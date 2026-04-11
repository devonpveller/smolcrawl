import dataclasses
import inspect
import sys

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"File: {dataclasses.__file__}")
try:
    print(f"Signature: {inspect.signature(dataclasses.dataclass)}")
except Exception as e:
    print(f"Could not get signature: {e}")

try:
    @dataclasses.dataclass(order=True)
    class Foo:
        pass
    print("Dataclass creation success")
except Exception as e:
    print(f"Dataclass creation failed: {e}")
