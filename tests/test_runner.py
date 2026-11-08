import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probe import hardware_vulkan
from runner import run


class RunnerTests(unittest.TestCase):
    def test_cpu_vulkan_and_missing_gpu_cannot_pass(self):
        self.assertFalse(hardware_vulkan('GPU0:\n vendorID = 0x10005\n deviceName = llvmpipe'))
        self.assertFalse(hardware_vulkan(''))
        self.assertFalse(hardware_vulkan('GPU0:\n llvmpipe\nGPU1:\n vendorID = 0x10de\n deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU'))
        self.assertTrue(hardware_vulkan('GPU0:\n vendorID = 0x10de\n deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU\n deviceName = NVIDIA'))

    @unittest.skipIf(os.name != 'posix', 'Linux process groups required')
    def test_process_success_failure_timeout_and_gpu_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = [('success', 'exit 0', 'smoke', 0, 'PROCESS_EXIT_ZERO'),
                     ('failure', 'exit 7', 'smoke', 1, 'PROCESS_FAILED'),
                     ('timeout', 'sleep 30', 'smoke', 1, 'PROCESS_FAILED'),
                     ('no-gpu', 'exit 0', 'gpu', 1, 'PREFLIGHT_FAILED')]
            for name, script, lane, expected, result in cases:
                with self.subTest(name=name):
                    exe = root / name
                    exe.write_text('#!/bin/sh\n' + script + '\n')
                    exe.chmod(0o755)
                    out = root / (name + '-results')
                    with patch('runner.probe', return_value={'gpu_preflight_pass': False}), patch('os.geteuid', return_value=1000):
                        self.assertEqual(run(str(exe), lane, 1, [], out), expected)
                    receipts = list(out.glob('*/receipt.json'))
                    self.assertEqual(len(receipts), 1)
                    receipt = json.loads(receipts[0].read_text())
                    self.assertEqual(receipt['result'], result)
                    self.assertEqual(receipt['timed_out'], name == 'timeout')
                    self.assertTrue(receipts[0].parent.joinpath('profile').is_dir())
                    self.assertIn('-SaveRoot=' + str(receipts[0].parent / 'profile'), receipt['argv'])
                    self.assertIn('-ScratchSession=' + receipts[0].parent.name, receipt['argv'])

    @unittest.skipIf(os.name != 'posix', 'Linux execution required')
    def test_lane_and_profile_override_rejected(self):
        with patch('os.geteuid', return_value=1000):
            for arg in ['-nullrhi', '-UserDir=/tmp/shared', '-graphicsadapter=1', '-SaveRoot=/tmp/shared', '-ScratchSession=other']:
                with self.subTest(arg=arg), self.assertRaises(ValueError):
                    run('/bin/true', 'gpu', 10, [arg], '/tmp/unused')


if __name__ == '__main__':
    unittest.main()
