import unittest

from shadow_wik.webui import api_settings


class RuntimeStub:
    def __init__(self):
        self.value = 0

    def set_validation_level(self, value):
        self.value = value
        return value


class SettingsApiTests(unittest.TestCase):
    def test_slider_accepts_zero_to_100(self):
        runtime = RuntimeStub()
        status, body = api_settings.handle(runtime, {"validation_level": 0})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["mode"], "exploration")
        status, body = api_settings.handle(runtime, {"validation_level": 100})
        self.assertEqual(status, 200)
        self.assertEqual(runtime.value, 100)

    def test_slider_rejects_out_of_range(self):
        status, _ = api_settings.handle(RuntimeStub(), {"validation_level": 101})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
