# z-llm-safety-gateway-sdk

Detector SDK for **z LLM Safety Gateway** — build third-party content safety detectors for the gateway.

The SDK provides the base classes, context, result models, and testing utilities you need to implement a detector that runs in-process inside the gateway (loaded via Python entry points).

## Install

```bash
git clone https://github.com/zergcq-cell/z-llm-safety-gateway.git
pip install -e ./z-llm-safety-gateway/sdk
```

v0.1.1 发布后，也可从 GitHub Release 下载并安装
`z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl`。SDK 当前未发布到 PyPI。

## Quick Start

```python
from typing import Any

from z_llm_safety_gateway_sdk import Detector, DetectionContext, DetectionResult


class MyDetector(Detector):
    name = "my_detector"
    category = "custom"
    description = "Blocks one example phrase"
    version = "0.1.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self.block_phrase = str(config.get("block_phrase", "bad word"))

    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        blocked = self.block_phrase in content
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="block" if blocked else "allow",
            confidence=0.95 if blocked else 0.0,
            risk_level="high" if blocked else "low",
            message="blocked phrase" if blocked else "passed",
        )
```

Register your detector in your plugin package's `pyproject.toml`:

```toml
[project.entry-points."z_llm_safety_gateway.detectors"]
my_detector = "my_package.detector:MyDetector"
```

For the current pre-1.0 SDK line, use the v0.1.1 GitHub Release wheel as a
direct dependency. Once the SDK is available from a package index, use a
normal pre-1.0 compatible version range.

## CLI Scaffolding

```bash
zlg-sdk new my-detector --type python   # scaffold an in-process detector project
zlg-sdk new my-detector --type grpc     # scaffold a gRPC sidecar detector project
```

See the main repository's [Plugin Development](../docs/plugin-development.md) guide for details.

## Versioning

The gateway and SDK are both released as 0.1.1 for this coordinated patch. They retain
independent version histories and are not required to use matching versions in future releases.
