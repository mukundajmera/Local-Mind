# DeviceManager - Intelligent Compute Resource Manager

Production-grade device selector with capability scoring for GPU/CPU selection across Windows, Linux, FreeBSD, and macOS.

## Features

- ✅ **Capability Scoring System** - Not just `is_available()` checks
- ✅ **Cross-Platform** - Windows, Linux, FreeBSD, macOS (Intel & Apple Silicon)
- ✅ **Multi-Backend** - CUDA, ROCm, Metal, Vulkan, OpenCL, DirectML, CPU
- ✅ **Graceful Fallback** - Automatic CPU fallback on GPU driver failures
- ✅ **Zero Silent Failures** - All errors logged with warnings

## Quick Start

```python
from device_manager import DeviceManager

# Get singleton instance
dm = DeviceManager.get_instance()

# Select best device
device = dm.get_best_device()

# Log device info
dm.log_device_info()

# Get PyTorch device string
pytorch_device = dm.get_pytorch_device()
model.to(pytorch_device)
```

## Capability Scoring Algorithm

```
score = base_score + memory_bonus + availability_penalty

Base Scores:
- Discrete GPU: 100 points
- Integrated GPU: 50 points  
- CPU: 10 points

Memory Bonus:
+1 point per GB of available VRAM (if queryable)

Availability Penalty:
If initialization fails: score = 0
```

## Platform Support Matrix

| Platform | Primary | Secondary | Fallback |
|----------|---------|-----------|----------|
| macOS (Apple Silicon) | Metal (MPS) | - | CPU |
| macOS (Intel) | - | - | CPU |
| Linux | CUDA | ROCm, OpenCL | CPU |
| Windows | CUDA | DirectML | CPU |
| FreeBSD | OpenCL | - | CPU |

## API Reference

### DeviceManager

#### `get_instance() -> DeviceManager`
Get singleton instance (thread-safe).

#### `get_best_device() -> DeviceInfo`
Select and return highest-scoring available device with error handling.

#### `get_all_devices() -> List[DeviceInfo]`
Get list of all discovered devices sorted by score.

#### `log_device_info() -> None`
Print detailed information about selected device.

#### `get_pytorch_device() -> str`
Get PyTorch device string (`"cuda"`, `"mps"`, or `"cpu"`).

### DeviceInfo

Dataclass containing device information:
- `name`: Device name (e.g., "Apple M3 Max", "NVIDIA RTX 4090")
- `device_type`: DeviceType enum (DISCRETE_GPU, INTEGRATED_GPU, CPU)
- `backend`: Backend enum (CUDA, METAL, CPU, etc.)
- `memory_gb`: Available memory in gigabytes
- `driver_version`: Driver version string
- `utilization`: Current utilization (0.0 to 1.0)
- `score`: Computed capability score
- `available`: Whether device initialized successfully
- `error`: Error message if initialization failed

## Testing

```bash
# Test on current platform
cd apps/backend
python test_device_manager.py
```

Expected output on macOS M3:
```
Selected Device: Apple M3 Max
Type: INTEGRATED_GPU
Backend: MPS
Memory: 36.00 GB
Driver: Metal
Score: 86
```

## Integration Example

```python
import torch
from device_manager import DeviceManager

# Initialize
dm = DeviceManager.get_instance()
device = dm.get_best_device()
dm.log_device_info()

# Use with PyTorch
device_str = dm.get_pytorch_device()
model = MyModel().to(device_str)
data = data.to(device_str)

# Inference
with torch.no_grad():
    output = model(data)
```

## Error Handling

The DeviceManager implements **strict error boundaries**:

```python
try:
    device = initialize_gpu()
except (RuntimeError, OSError) as e:
    logger.warning(f"GPU init failed: {e}. Falling back to CPU")
    device = initialize_cpu()
```

This ensures:
- Application never crashes from GPU driver issues
- User is notified via warning logs
- Automatic fallback to next best device (usually CPU)

## Dependencies

**Required:**
- `psutil` - CPU information

**Optional (for GPU detection):**
- `torch` - CUDA, ROCm, Metal (MPS)
- `pynvml` - NVIDIA GPU utilization
- `pyopencl` - OpenCL devices

## Configuration

Set environment variables to control behavior:

```bash
# Force CPU only (bypass GPU detection)
export DEVICE_SELECTION_MODE=cpu-only

# Enable debug logging
export LOG_LEVEL=DEBUG
```

## License

MIT License - See LICENSE file for details.
