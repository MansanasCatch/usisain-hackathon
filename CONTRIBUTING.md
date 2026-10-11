# Contributing to UsisAIn

This guide explains how to extend UsisAIn with new pipeline steps and LLM providers while preserving the architectural boundaries.

## Adding a New Pipeline Step

### 1. Define Step Inputs and Outputs
Create typed dataclasses in `mcp_server/steps/base.py` extending `BaseStep`:

```python
from dataclasses import dataclass
from typing import Any


@dataclass
class Step6Input:
    claim_text: str
    metadata: dict[str, Any]


@dataclass
class Step6Output:
    status: str
    score: float
```

### 2. Implement the Step Module
Create `mcp_server/steps/step6/step.py`:

```python
from mcp_server.steps.base import BaseStep, Step6Input, Step6Output


class Step6(BaseStep[Step6Input, Step6Output]):
    async def run(self, input_data: Step6Input) -> Step6Output:
        return Step6Output(status="complete", score=1.0)
```

### 3. Expose the Step Adapter
Add an adapter in `mcp_server/tools/step6.py` and register the step with the runner in `backend-api/src/usisain_backend/orchestration/step_runner.py`.

### 4. Update the Dashboard Pipeline Info
Add the step's metadata to `client/web-app/dashboard/modules/step_info.js` to expose its documentation in the dashboard UI.

---

## Adding a New LLM Provider

### 1. Inherit from `BaseLLMProvider`
Implement the abstract interface in `mcp_server/services/llm/provider_name.py`:

```python
from mcp_server.services.llm.base import BaseLLMProvider


class CustomProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, **kwargs) -> str:
        return "Generated response"

    def is_available(self) -> bool:
        return bool(self.api_key)
```

### 2. Register in the Provider Factory
Add the provider to `mcp_server/services/llm/factory.py`:

```python
from mcp_server.core.enums import Provider


def get_provider(provider_type: Provider):
    if provider_type == Provider.CUSTOM:
        return CustomProvider(...)
```

### 3. Add Provider Configuration
Update `backend-api/src/usisain_backend/core/config.py` and `backend-api/src/usisain_backend/core/enums.py` to recognize the new provider name and its API keys.
