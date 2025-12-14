"""
Intelligent Compute Resource Manager
=====================================

Cross-platform device selector with capability scoring system.
Supports: Windows, Linux, FreeBSD, macOS (Intel & Apple Silicon)

Author: Local Mind Team
License: MIT
"""

import logging
import platform
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Device types with base scoring"""
    DISCRETE_GPU = 100
    INTEGRATED_GPU = 50
    CPU = 10
    UNKNOWN = 0


class Backend(Enum):
    """Available compute backends"""
    CUDA = "cuda"
    ROCM = "rocm"
    METAL = "mps"  # Metal Performance Shaders
    VULKAN = "vulkan"
    OPENCL = "opencl"
    DIRECTX = "directml"
    CPU = "cpu"


@dataclass
class DeviceInfo:
    """Device information container"""
    name: str
    device_type: DeviceType
    backend: Backend
    memory_gb: float
    driver_version: str
    utilization: float  # 0.0 to 1.0
    score: int
    available: bool
    error: Optional[str] = None

    def __repr__(self):
        return (f"DeviceInfo(name='{self.name}', type={self.device_type.name}, "
                f"backend={self.backend.value}, memory={self.memory_gb}GB, "
                f"score={self.score}, available={self.available})")


class DeviceManager:
    """
    Singleton Device Manager with Intelligent Selection
    
    Usage:
        dm = DeviceManager.get_instance()
        device = dm.get_best_device()
        dm.log_device_info()
    """
    
    _instance: Optional['DeviceManager'] = None
    _initialized: bool = False
    
    def __init__(self):
        if DeviceManager._initialized:
            return
            
        self.platform = platform.system()
        self.architecture = platform.machine()
        self.devices: List[DeviceInfo] = []
        self.selected_device: Optional[DeviceInfo] = None
        
        logger.info(f"DeviceManager initializing on {self.platform} ({self.architecture})")
        
        # Run discovery
        self._discover_devices()
        
        DeviceManager._initialized = True
    
    @staticmethod
    def get_instance() -> 'DeviceManager':
        """Get singleton instance"""
        if DeviceManager._instance is None:
            DeviceManager._instance = DeviceManager()
        return DeviceManager._instance
    
    def _discover_devices(self) -> None:
        """Discovery Phase: Scan all available backends"""
        logger.info("🔍 Starting device discovery...")
        
        # Platform-specific discovery
        if self.platform == "Darwin":  # macOS
            self._discover_macos()
        elif self.platform == "Linux":
            self._discover_linux()
        elif self.platform == "Windows":
            self._discover_windows()
        elif "BSD" in self.platform:
            self._discover_bsd()
        else:
            logger.warning(f"Unknown platform: {self.platform}")
        
        # Always add CPU as fallback
        self._discover_cpu()
        
        # Sort by score (highest first)
        self.devices.sort(key=lambda d: d.score, reverse=True)
        
        logger.info(f"✅ Discovered {len(self.devices)} device(s)")
    
    def _discover_macos(self) -> None:
        """macOS-specific device discovery"""
        # Check for Apple Silicon (M1/M2/M3)
        if self.architecture == "arm64":
            self._check_metal_mps()
        else:
            logger.info("macOS Intel - GPU acceleration limited")
    
    def _discover_linux(self) -> None:
        """Linux-specific device discovery"""
        # Priority: CUDA > ROCm > OpenCL
        self._check_cuda()
        self._check_rocm()
        self._check_opencl()
    
    def _discover_windows(self) -> None:
        """Windows-specific device discovery"""
        # Priority: CUDA > DirectML
        self._check_cuda()
        self._check_directml()
    
    def _discover_bsd(self) -> None:
        """FreeBSD-specific device discovery"""
        logger.warning("FreeBSD: Limited GPU driver support")
        # Try OpenCL as best option
        self._check_opencl()
    
    def _check_metal_mps(self) -> None:
        """Check for Metal Performance Shaders (Apple Silicon)"""
        try:
            import torch
            if torch.backends.mps.is_available():
                # Get chip info from platform
                chip_name = os.popen("sysctl -n machdep.cpu.brand_string").read().strip()
                
                # Apple Silicon has unified memory
                memory_gb = self._get_system_memory_gb()
                
                device = DeviceInfo(
                    name=chip_name or "Apple Silicon",
                    device_type=DeviceType.INTEGRATED_GPU,  # Unified architecture
                    backend=Backend.METAL,
                    memory_gb=memory_gb,
                    driver_version="Metal",
                    utilization=0.0,
                    score=DeviceType.INTEGRATED_GPU.value + int(memory_gb),
                    available=True
                )
                self.devices.append(device)
                logger.info(f"✓ Metal MPS: {device.name}")
            else:
                logger.info("✗ Metal MPS not available")
        except ImportError:
            logger.warning("PyTorch not installed - cannot detect Metal")
        except Exception as e:
            logger.warning(f"Metal detection failed: {e}")
    
    def _check_cuda(self) -> None:
        """Check for NVIDIA CUDA"""
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    memory_gb = props.total_memory / (1024**3)
                    
                    # Try to get utilization
                    utilization = 0.0
                    try:
                        import pynvml
                        pynvml.nvmlInit()
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        utilization = util.gpu / 100.0
                        pynvml.nvmlShutdown()
                    except:
                        pass
                    
                    device = DeviceInfo(
                        name=props.name,
                        device_type=DeviceType.DISCRETE_GPU,
                        backend=Backend.CUDA,
                        memory_gb=memory_gb,
                        driver_version=torch.version.cuda or "unknown",
                        utilization=utilization,
                        score=DeviceType.DISCRETE_GPU.value + int(memory_gb) - int(utilization * 10),
                        available=True
                    )
                    self.devices.append(device)
                    logger.info(f"✓ CUDA GPU {i}: {device.name}")
            else:
                logger.info("✗ CUDA not available")
        except ImportError:
            logger.info("✗ PyTorch not installed - cannot detect CUDA")
        except Exception as e:
            logger.warning(f"CUDA detection failed: {e}")
    
    def _check_rocm(self) -> None:
        """Check for AMD ROCm"""
        try:
            import torch
            if hasattr(torch, 'hip') and torch.hip.is_available():
                for i in range(torch.hip.device_count()):
                    props = torch.hip.get_device_properties(i)
                    memory_gb = props.total_memory / (1024**3)
                    
                    device = DeviceInfo(
                        name=props.name,
                        device_type=DeviceType.DISCRETE_GPU,
                        backend=Backend.ROCM,
                        memory_gb=memory_gb,
                        driver_version="ROCm",
                        utilization=0.0,
                        score=DeviceType.DISCRETE_GPU.value + int(memory_gb),
                        available=True
                    )
                    self.devices.append(device)
                    logger.info(f"✓ ROCm GPU {i}: {device.name}")
            else:
                logger.info("✗ ROCm not available")
        except Exception as e:
            logger.info(f"✗ ROCm detection failed: {e}")
    
    def _check_opencl(self) -> None:
        """Check for OpenCL devices"""
        try:
            import pyopencl as cl
            platforms = cl.get_platforms()
            for platform in platforms:
                for device in platform.get_devices():
                    memory_gb = device.global_mem_size / (1024**3)
                    
                    # Determine if discrete or integrated
                    is_gpu = device.type == cl.device_type.GPU
                    dev_type = DeviceType.DISCRETE_GPU if is_gpu else DeviceType.CPU
                    
                    device_info = DeviceInfo(
                        name=device.name.strip(),
                        device_type=dev_type,
                        backend=Backend.OPENCL,
                        memory_gb=memory_gb,
                        driver_version=device.driver_version,
                        utilization=0.0,
                        score=dev_type.value + int(memory_gb),
                        available=True
                    )
                    self.devices.append(device_info)
                    logger.info(f"✓ OpenCL: {device_info.name}")
        except ImportError:
            logger.info("✗ PyOpenCL not installed")
        except Exception as e:
            logger.info(f"✗ OpenCL detection failed: {e}")
    
    def _check_directml(self) -> None:
        """Check for DirectML (Windows)"""
        logger.info("✗ DirectML detection not implemented yet")
    
    def _discover_cpu(self) -> None:
        """CPU is always available as fallback"""
        try:
            import psutil
            memory_gb = psutil.virtual_memory().total / (1024**3)
            utilization = psutil.cpu_percent(interval=0.1) / 100.0
        except ImportError:
            # Fallback without psutil
            memory_gb = 0.0
            utilization = 0.0
        
        cpu_name = platform.processor() or "CPU"
        
        device = DeviceInfo(
            name=f"{cpu_name} ({os.cpu_count()} cores)",
            device_type=DeviceType.CPU,
            backend=Backend.CPU,
            memory_gb=memory_gb,
            driver_version="N/A",
            utilization=utilization,
            score=DeviceType.CPU.value,
            available=True
        )
        self.devices.append(device)
        logger.info(f"✓ CPU: {device.name}")
    
    def _get_system_memory_gb(self) -> float:
        """Get total system memory"""
        try:
            import psutil
            return psutil.virtual_memory().total / (1024**3)
        except ImportError:
            return 0.0
        except Exception:
            return 0.0
    
    def get_best_device(self) -> DeviceInfo:
        """
        Selection Phase: Get highest-scoring available device
        
        Returns:
            DeviceInfo: Best device with error handling
        """
        if not self.devices:
            raise RuntimeError("No devices available!")
        
        # Try devices in order of score
        for device in self.devices:
            if not device.available:
                continue
            
            try:
                # Test initialization
                if self._test_device(device):
                    self.selected_device = device
                    logger.info(f"✅ Selected: {device.name} (score: {device.score})")
                    return device
                else:
                    logger.warning(f"Device test failed: {device.name}")
                    device.available = False
            except Exception as e:
                logger.warning(f"Device init failed: {device.name} - {e}")
                device.available = False
                device.error = str(e)
        
        # Should never reach here since CPU is always available
        raise RuntimeError("All devices failed to initialize!")
    
    def _test_device(self, device: DeviceInfo) -> bool:
        """Test if device can be initialized"""
        try:
            if device.backend == Backend.METAL:
                import torch
                return torch.backends.mps.is_available()
            elif device.backend == Backend.CUDA:
                import torch
                return torch.cuda.is_available()
            elif device.backend == Backend.CPU:
                return True
            else:
                return True
        except Exception as e:
            logger.debug(f"Device test error: {e}")
            return False
    
    def get_all_devices(self) -> List[DeviceInfo]:
        """Get list of all discovered devices"""
        return self.devices.copy()
    
    def log_device_info(self) -> None:
        """Log detailed information about selected device"""
        if not self.selected_device:
            logger.warning("No device selected yet!")
            return
        
        d = self.selected_device
        
        logger.info("=" * 60)
        logger.info(f"Selected Device: {d.name}")
        logger.info(f"Type: {d.device_type.name}")
        logger.info(f"Backend: {d.backend.value.upper()}")
        logger.info(f"Memory: {d.memory_gb:.2f} GB")
        logger.info(f"Driver: {d.driver_version}")
        logger.info(f"Score: {d.score}")
        if d.utilization > 0:
            logger.info(f"Utilization: {d.utilization*100:.1f}%")
        logger.info("=" * 60)
    
    def get_pytorch_device(self) -> str:
        """Get PyTorch device string for selected device"""
        if not self.selected_device:
            self.get_best_device()
        
        backend_map = {
            Backend.CUDA: "cuda",
            Backend.METAL: "mps",
            Backend.CPU: "cpu",
        }
        
        device_str = backend_map.get(self.selected_device.backend, "cpu")
        logger.info(f"PyTorch device: {device_str}")
        return device_str


# Convenience function
def get_best_device() -> DeviceInfo:
    """Convenience function to get best device"""
    dm = DeviceManager.get_instance()
    return dm.get_best_device()
