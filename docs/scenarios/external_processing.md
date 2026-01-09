```mermaid
flowchart LR
%% Nodes
    A("Test runner")
    B("Proxy (Envoy or HAProxy)")
    C("Go security processor")
    D("HTTP app")
    E("Proxy")
    F("Agent")
    G("Backend")

%% Edge connections between nodes
    A --> B --> D
    B --> C --> B
    C --> E --> F --> G
    %% D -- Mermaid js --> I --> J
```