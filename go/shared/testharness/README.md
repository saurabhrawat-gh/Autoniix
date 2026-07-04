# Go Service Test Harness

Per `HARNESS-ENGINEERING-PLAN.md §A7`.

Provides two tools for testing Go microservices (Research, Script, Voice, Image, etc.):

1. **`ServiceHarness`** — in-process gRPC test server over `bufconn` (no TCP port needed)
2. **`GoldenLoader`** — loads and asserts against golden-file fixtures from `tests/golden/`

## ServiceHarness

```go
import "autoniix/go/shared/testharness"

func TestMyService(t *testing.T) {
    h := testharness.New(t, "research")
    defer h.Close()

    // Register your service implementation on h.Server
    pb.RegisterResearchServiceServer(h.Server, &MyResearchService{LLM: h.MockLLM})

    client := pb.NewResearchServiceClient(h.Conn)
    resp, err := client.Research(context.Background(), &pb.ResearchRequest{Topic: "AI"})
    assert.NoError(t, err)
    assert.NotEmpty(t, resp.Summary)
}
```

### MockLLMProvider

`ServiceHarness` includes a pre-wired `MockLLMProvider` with deterministic responses:

| Keyword in prompt | Response |
|---|---|
| `"research"` | `{"selected_topic": "Mock Topic", ...}` |
| `"script"` | `{"title": "Mock Script", "segments": [...]}` |
| _(default)_ | `{"result": "mock_response", "score": 8.5, "pass": true}` |

```go
// Override for a specific test:
h.MockLLM.SetResponse("my-keyword", `{"custom": "response"}`)
h.MockLLM.Reset() // restore defaults
```

## GoldenLoader

```go
func TestEquivalenceAuthMode(t *testing.T) {
    g := testharness.NewGoldenLoader(t, "../../tests/golden")

    // Load fixture
    fixture := g.Load("auth/auth_mode")

    // Make HTTP request
    resp, err := http.Get(gatewayURL + fixture.Path)
    require.NoError(t, err)
    defer resp.Body.Close()

    // Assert status
    g.AssertStatus(fixture, resp)

    // Assert body subset (ignores IgnoreFields like timestamps)
    var body map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&body)
    g.AssertBodySubset(fixture, body)
}
```

### Listing all fixtures

```go
names := g.List()
// e.g. ["auth/auth_mode", "channels/channels_list", ...]
```

## Running tests

```bash
# From repo root
go test ./go/shared/testharness/... -v

# Or via make
make test-go-harness
```

## Golden fixture format

See `tests/golden/README.md` for the full JSON schema.

Quick reference:
```json
{
  "method": "GET",
  "path": "/api/v2/auth/mode",
  "request_body": null,
  "status": 200,
  "body": { "mode": "email" },
  "ignore_fields": ["created_at", "updated_at", "id"]
}
```
