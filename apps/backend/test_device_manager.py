#!/usr/bin/env python3
"""
DeviceManager Test Script
==========================

Tests the intelligent device selector on current platform.

Usage:
    python test_device_manager.py
"""

import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

def main():
    """Test DeviceManager functionality"""
    try:
        # Import DeviceManager
        from device_manager import DeviceManager, get_best_device
        
        logger.info("=" * 70)
        logger.info("DEVICEMANAGER TEST - Intelligent Compute Resource Selection")
        logger.info("=" * 70)
        
        # Get singleton instance
        dm = DeviceManager.get_instance()
        
        # Show all discovered devices
        logger.info("\n📋 DISCOVERED DEVICES:")
        logger.info("-" * 70)
        
        devices = dm.get_all_devices()
        for i, device in enumerate(devices, 1):
            status = "✓ Available" if device.available else "✗ Unavailable"
            logger.info(f"{i}. {device.name}")
            logger.info(f"   Type: {device.device_type.name} | Backend: {device.backend.value}")
            logger.info(f"   Memory: {device.memory_gb:.2f} GB | Score: {device.score} | {status}")
            if device.error:
                logger.info(f"   Error: {device.error}")
            logger.info("")
        
        # Get best device
        logger.info("\n🎯 SELECTING BEST DEVICE:")
        logger.info("-" * 70)
        
        best_device = dm.get_best_device()
        dm.log_device_info()
        
        # Get PyTorch device string
        pytorch_device = dm.get_pytorch_device()
        logger.info(f"\n💡 Use in PyTorch: model.to('{pytorch_device}')")
        
        # Test actual PyTorch if available
        logger.info("\n🧪 TESTING PYTORCH INTEGRATION:")
        logger.info("-" * 70)
        
        try:
            import torch
            
            # Create test tensor
            test_tensor = torch.randn(1000, 1000)
            device_tensor = test_tensor.to(pytorch_device)
            
            logger.info(f"✓ Created test tensor on {pytorch_device}")
            logger.info(f"  Tensor shape: {device_tensor.shape}")
            logger.info(f"  Tensor device: {device_tensor.device}")
            
            # Simple computation test
            result = torch.matmul(device_tensor, device_tensor)
            logger.info(f"✓ Matrix multiplication successful")
            
        except ImportError:
            logger.warning("PyTorch not installed - skipping integration test")
        except Exception as e:
            logger.error(f"PyTorch test failed: {e}")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ DEVICEMANAGER TEST COMPLETE")
        logger.info("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
