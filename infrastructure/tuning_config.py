"""
Sovereign Cognitive Engine - Inference Optimizer
=================================================
Dynamic tuning of AI engines (vLLM, Kokoro) based on available hardware.

Usage:
    from infrastructure.tuning_config import get_vllm_config, get_kokoro_config
    
    vllm_args = get_vllm_config()
    # {'gpu_memory_utilization': 0.7, 'max_model_len': 4096, ...}
"""

import os
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


# =============================================================================
# Hardware Detection
# =============================================================================

@dataclass
class GPUInfo:
    """Information about a single GPU."""
    index: int
    name: str
    total_memory_mb: int
    free_memory_mb: int
    utilization_percent: int
    temperature_c: int = 0
    
    @property
    def used_memory_mb(self) -> int:
        return self.total_memory_mb - self.free_memory_mb
    
    @property
    def memory_utilization(self) -> float:
        return self.used_memory_mb / self.total_memory_mb if self.total_memory_mb > 0 else 0


@dataclass
class SystemResources:
    """Detected system resources."""
    gpus: List[GPUInfo] = field(default_factory=list)
    cpu_count: int = 0
    total_ram_gb: float = 0
    
    @property
    def total_gpu_memory_mb(self) -> int:
        return sum(gpu.total_memory_mb for gpu in self.gpus)
    
    @property
    def total_free_gpu_memory_mb(self) -> int:
        return sum(gpu.free_memory_mb for gpu in self.gpus)
    
    @property
    def primary_gpu(self) -> Optional[GPUInfo]:
        return self.gpus[0] if self.gpus else None


def detect_gpu_resources() -> List[GPUInfo]:
    """Detect NVIDIA GPU resources using nvidia-smi."""
    gpus = []
    
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append(GPUInfo(
                        index=int(parts[0]),
                        name=parts[1],
                        total_memory_mb=int(parts[2]),
                        free_memory_mb=int(parts[3]),
                        utilization_percent=int(parts[4]),
                        temperature_c=int(parts[5]) if len(parts) > 5 else 0,
                    ))
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.warning(f"GPU detection failed: {e}")
    
    return gpus


def detect_system_resources() -> SystemResources:
    """Detect all system resources."""
    import multiprocessing
    
    resources = SystemResources(
        gpus=detect_gpu_resources(),
        cpu_count=multiprocessing.cpu_count(),
    )
    
    # Detect RAM
    try:
        import psutil
        resources.total_ram_gb = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        # Fallback for Linux
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        resources.total_ram_gb = kb / (1024**2)
                        break
        except:
            pass
    
    return resources


# =============================================================================
# vLLM Configuration
# =============================================================================

@dataclass
class VLLMConfig:
    """vLLM server configuration."""
    
    # Memory management
    gpu_memory_utilization: float = 0.7  # Reserve 30% for TTS
    
    # Model configuration
    max_model_len: int = 4096
    dtype: str = "auto"
    
    # Performance tuning
    enforce_eager: bool = False  # False = use CUDA Graphs
    enable_prefix_caching: bool = True
    
    # Batching
    max_num_seqs: int = 256
    max_num_batched_tokens: int = 8192
    
    # Quantization (optional)
    quantization: Optional[str] = None  # "awq", "gptq", None
    
    # Parallelism
    tensor_parallel_size: int = 1
    
    def to_args(self) -> List[str]:
        """Convert to command line arguments."""
        args = [
            f"--gpu-memory-utilization={self.gpu_memory_utilization}",
            f"--max-model-len={self.max_model_len}",
            f"--dtype={self.dtype}",
            f"--max-num-seqs={self.max_num_seqs}",
            f"--max-num-batched-tokens={self.max_num_batched_tokens}",
        ]
        
        if not self.enforce_eager:
            args.append("--enforce-eager=False")
        
        if self.enable_prefix_caching:
            args.append("--enable-prefix-caching")
        
        if self.quantization:
            args.append(f"--quantization={self.quantization}")
        
        if self.tensor_parallel_size > 1:
            args.append(f"--tensor-parallel-size={self.tensor_parallel_size}")
        
        return args
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API usage."""
        return {
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "max_model_len": self.max_model_len,
            "dtype": self.dtype,
            "enforce_eager": self.enforce_eager,
            "enable_prefix_caching": self.enable_prefix_caching,
            "max_num_seqs": self.max_num_seqs,
            "max_num_batched_tokens": self.max_num_batched_tokens,
            "quantization": self.quantization,
            "tensor_parallel_size": self.tensor_parallel_size,
        }


def get_vllm_config(resources: Optional[SystemResources] = None) -> VLLMConfig:
    """
    Generate optimal vLLM configuration based on hardware.
    
    Key decisions:
    - GPU memory: Reserve 30% for Kokoro TTS
    - Max model len: 8192 if >12GB free, else 4096
    - CUDA Graphs: Enabled for speed
    """
    if resources is None:
        resources = detect_system_resources()
    
    config = VLLMConfig()
    
    # GPU-based tuning
    if resources.primary_gpu:
        gpu = resources.primary_gpu
        free_mb = gpu.free_memory_mb
        
        logger.info(f"Detected GPU: {gpu.name} ({gpu.total_memory_mb}MB total, {free_mb}MB free)")
        
        # Reserve 30% for TTS
        config.gpu_memory_utilization = 0.7
        
        # Dynamic max_model_len based on available VRAM
        # 8192 tokens requires ~4-6GB for 7B model
        if free_mb >= 16000:  # 16GB+ free
            config.max_model_len = 8192
            config.max_num_batched_tokens = 16384
        elif free_mb >= 12000:  # 12GB+ free
            config.max_model_len = 8192
            config.max_num_batched_tokens = 8192
        elif free_mb >= 8000:  # 8GB+ free
            config.max_model_len = 4096
            config.max_num_batched_tokens = 8192
        else:  # Less than 8GB
            config.max_model_len = 2048
            config.max_num_batched_tokens = 4096
            config.gpu_memory_utilization = 0.8  # Use more aggressively
        
        # Multi-GPU setup
        if len(resources.gpus) > 1:
            config.tensor_parallel_size = len(resources.gpus)
            logger.info(f"Multi-GPU detected: tensor_parallel_size={config.tensor_parallel_size}")
    else:
        logger.warning("No GPU detected! Using conservative defaults.")
        config.max_model_len = 2048
        config.max_num_batched_tokens = 2048
    
    # CUDA Graphs for performance
    config.enforce_eager = False
    
    logger.info(f"vLLM config: max_model_len={config.max_model_len}, gpu_util={config.gpu_memory_utilization}")
    
    return config


# =============================================================================
# Kokoro TTS Configuration
# =============================================================================

@dataclass
class KokoroConfig:
    """Kokoro TTS configuration."""
    
    # PyTorch precision
    float32_matmul_precision: str = "medium"  # "highest", "high", "medium"
    
    # Batching
    enable_smart_batching: bool = True
    max_batch_size: int = 8
    min_batch_chars: int = 100  # Don't batch very short texts
    batch_timeout_ms: int = 50  # Max wait time for batching
    
    # Memory
    max_audio_length_seconds: int = 300  # 5 minutes max
    
    # Quality vs Speed
    num_inference_steps: int = 50  # Reduce for speed
    
    def to_env_vars(self) -> Dict[str, str]:
        """Convert to environment variables."""
        return {
            "TORCH_MATMUL_PRECISION": self.float32_matmul_precision,
            "KOKORO_ENABLE_BATCHING": str(self.enable_smart_batching).lower(),
            "KOKORO_MAX_BATCH_SIZE": str(self.max_batch_size),
            "KOKORO_BATCH_TIMEOUT_MS": str(self.batch_timeout_ms),
            "KOKORO_MAX_AUDIO_LENGTH": str(self.max_audio_length_seconds),
        }


def get_kokoro_config(resources: Optional[SystemResources] = None) -> KokoroConfig:
    """Generate optimal Kokoro TTS configuration."""
    if resources is None:
        resources = detect_system_resources()
    
    config = KokoroConfig()
    
    # Tensor Core optimization for Ampere+ GPUs
    if resources.primary_gpu:
        gpu_name = resources.primary_gpu.name.lower()
        
        # Check for Tensor Core capable GPUs
        if any(x in gpu_name for x in ["a100", "h100", "a6000", "rtx 30", "rtx 40", "rtx 3", "rtx 4"]):
            config.float32_matmul_precision = "medium"
            logger.info("Tensor Core GPU detected: using medium precision for matmul")
        else:
            config.float32_matmul_precision = "highest"
    
    # Batching based on VRAM
    if resources.total_free_gpu_memory_mb >= 4000:
        config.max_batch_size = 8
    elif resources.total_free_gpu_memory_mb >= 2000:
        config.max_batch_size = 4
    else:
        config.max_batch_size = 2
        config.enable_smart_batching = False  # Disable if very low memory
    
    return config


def apply_torch_optimizations(config: KokoroConfig):
    """
    Apply PyTorch optimizations at runtime.
    Call this in the TTS service startup.
    """
    try:
        import torch
        
        # Set precision for Tensor Core acceleration
        torch.set_float32_matmul_precision(config.float32_matmul_precision)
        logger.info(f"Set torch matmul precision: {config.float32_matmul_precision}")
        
        # Enable TF32 on Ampere GPUs
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        
        # Optimize for inference
        if hasattr(torch, "inference_mode"):
            logger.info("PyTorch inference optimizations applied")
    except ImportError:
        logger.warning("PyTorch not available for optimization")


# =============================================================================
# Smart Batching for TTS
# =============================================================================

class SmartBatcher:
    """
    Batches short TTS requests to reduce kernel launch overhead.
    
    Usage:
        batcher = SmartBatcher(config)
        
        # Add sentences (may not process immediately)
        for sentence in sentences:
            batcher.add(sentence, speaker)
        
        # Force process remaining
        results = await batcher.flush()
    """
    
    def __init__(self, config: KokoroConfig):
        self.config = config
        self.pending: List[Dict[str, Any]] = []
        self.total_chars: int = 0
    
    def should_batch(self, text: str) -> bool:
        """Check if text should be batched or processed immediately."""
        if not self.config.enable_smart_batching:
            return False
        
        # Don't batch long texts
        if len(text) > 500:
            return False
        
        return True
    
    def add(self, text: str, speaker: str, **metadata) -> Optional[List[Dict]]:
        """
        Add text to batch. Returns batch if ready for processing.
        """
        if not self.should_batch(text):
            return [{"text": text, "speaker": speaker, **metadata}]
        
        self.pending.append({"text": text, "speaker": speaker, **metadata})
        self.total_chars += len(text)
        
        # Check if batch is ready
        if (
            len(self.pending) >= self.config.max_batch_size or
            self.total_chars >= self.config.min_batch_chars * self.config.max_batch_size
        ):
            return self.get_batch()
        
        return None
    
    def get_batch(self) -> List[Dict]:
        """Get current batch and reset."""
        batch = self.pending
        self.pending = []
        self.total_chars = 0
        return batch
    
    def has_pending(self) -> bool:
        return len(self.pending) > 0


# =============================================================================
# Configuration Export
# =============================================================================

def export_compose_env(
    vllm_config: VLLMConfig,
    kokoro_config: KokoroConfig,
    output_path: str = ".env.tuning",
):
    """Export configurations as environment variables for compose."""
    lines = [
        "# Auto-generated tuning configuration",
        f"# Generated based on detected hardware",
        "",
        "# vLLM Settings",
        f"VLLM_GPU_MEMORY_UTILIZATION={vllm_config.gpu_memory_utilization}",
        f"VLLM_MAX_MODEL_LEN={vllm_config.max_model_len}",
        f"VLLM_ENFORCE_EAGER={str(vllm_config.enforce_eager).lower()}",
        f"VLLM_TENSOR_PARALLEL_SIZE={vllm_config.tensor_parallel_size}",
        "",
        "# Kokoro TTS Settings",
    ]
    
    for key, value in kokoro_config.to_env_vars().items():
        lines.append(f"{key}={value}")
    
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    
    logger.info(f"Exported tuning config to {output_path}")


# =============================================================================
# CLI Interface
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Inference Optimizer")
    parser.add_argument("--detect", action="store_true", help="Detect and display hardware")
    parser.add_argument("--export", type=str, help="Export config to file")
    parser.add_argument("--vllm-args", action="store_true", help="Print vLLM CLI args")
    
    args = parser.parse_args()
    
    resources = detect_system_resources()
    
    if args.detect or not any([args.export, args.vllm_args]):
        print("=" * 60)
        print("Detected System Resources")
        print("=" * 60)
        print(f"CPUs: {resources.cpu_count}")
        print(f"RAM: {resources.total_ram_gb:.1f} GB")
        print()
        
        for gpu in resources.gpus:
            print(f"GPU {gpu.index}: {gpu.name}")
            print(f"  Memory: {gpu.used_memory_mb}MB / {gpu.total_memory_mb}MB")
            print(f"  Utilization: {gpu.utilization_percent}%")
            print(f"  Temperature: {gpu.temperature_c}°C")
        
        if not resources.gpus:
            print("No NVIDIA GPUs detected")
    
    vllm_config = get_vllm_config(resources)
    kokoro_config = get_kokoro_config(resources)
    
    if args.vllm_args:
        print(" ".join(vllm_config.to_args()))
    
    if args.export:
        export_compose_env(vllm_config, kokoro_config, args.export)
