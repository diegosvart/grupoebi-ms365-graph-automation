# Estrategia de Testing

## Principios

- Todos los tests usan **datos ficticios**. Ningun fixture contiene emails, GUIDs o nombres reales de produccion.
- Las llamadas a la Graph API se **mockean** en tests unitarios. Los tests de integracion se ejecutan contra un tenant de desarrollo separado.
- El modo `--dry-run` del CLI sirve como smoke test antes de ejecutar en produccion.
- **Cobertura minima:** 80% sobre los modulos de logica de negocio (`parse_csv`, `resolve_email`, transformaciones).

---

## Estructura de tests

```
tests/
|-- conftest.py                    # Fixtures compartidos y configuracion de pytest
|-- fixtures/                      # Datos de prueba ficticios
|   |-- sample_full.csv            # Plan completo: encabezado + buckets + tareas
|   |-- sample_plan_only.csv       # Solo encabezado del plan
|   |-- sample_tasks_only.csv      # Solo tareas
|   |-- invalid_date.csv           # Fecha en formato incorrecto
|   |-- invalid_priority.csv       # Prioridad no reconocida
|   `-- empty.csv                  # CSV vacio
|
|-- test_graph_api.py              # Tests de la funcion graph_request()
|-- test_orchestrators.py          # Tests de los flujos de orquestacion
|-- test_transforms.py             # Tests de parse_csv y transformaciones
`-- test_create_environment.py     # Tests del orquestador de entorno de proyecto
```

---

## Como ejecutar los tests

### Todos los tests

```bash
pytest
```

### Test especifico

```bash
pytest tests/test_graph_api.py -v
```

### Solo listar tests sin ejecutar

```bash
pytest --co -q
```

### Con reporte de cobertura

```bash
pytest --cov=. --cov-report=term-missing
```

### Solo tests marcados como rapidos (sin red)

```bash
pytest -m "not integration"
```

---

## Categorias de tests

### Tests unitarios (sin red, sin credenciales)

Cubren la logica de negocio pura que no depende de la Graph API:

- `test_transforms.py`: `parse_csv()`, normalizacion de prioridades, conversion de fechas
- `test_graph_api.py`: manejo de errores HTTP, logica de retry en 429, renovacion de token

Estos tests usan `pytest-mock` para mockear las llamadas HTTP:

```python
# Ejemplo de test unitario con mock
def test_parse_csv_valid_full(tmp_path):
    csv_content = "PlanName;BucketName;TaskTitle;AssignedTo;DueDate;Priority\n"
    csv_content += "Test Plan;Inicio;Primera tarea;usuario@empresa.com;01042026;urgent\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    rows = parse_csv(str(csv_file))
    assert len(rows) == 1
    assert rows[0]["PlanName"] == "Test Plan"
    assert rows[0]["Priority"] == "urgent"
```

```python
# Ejemplo de test de retry en throttling
def test_graph_request_retries_on_429(mocker):
    mock_response_429 = mocker.MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}

    mock_response_200 = mocker.MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"value": []}

    mock_client = mocker.patch("httpx.Client.get",
                               side_effect=[mock_response_429, mock_response_200])

    result = graph_request("GET", "/test")
    assert mock_client.call_count == 2
    assert result == {"value": []}
```

### Tests de integracion (requieren credenciales de desarrollo)

Se ejecutan contra un tenant de Azure AD de desarrollo/sandbox, no de produccion.

**Requisitos:**
- Archivo `.env.test` con credenciales del tenant de desarrollo
- Variable de entorno `RUN_INTEGRATION_TESTS=true`

```bash
RUN_INTEGRATION_TESTS=true pytest -m integration
```

**Que cubren:**
- Crear y eliminar un plan de Planner real
- Resolver un email real a GUID
- Verificar autenticacion via Client Credentials Flow

---

## Fixtures compartidos (conftest.py)

```python
import pytest

@pytest.fixture
def mock_auth_token(mocker):
    """Token JWT ficticio para tests que no llaman a la Graph API real."""
    mocker.patch(
        "auth.MicrosoftAuthManager.get_token",
        return_value="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.FAKE.TOKEN"
    )

@pytest.fixture
def sample_csv_path(tmp_path):
    """CSV de prueba minimo con datos ficticios."""
    csv_content = (
        "PlanName;BucketName;TaskTitle;AssignedTo;DueDate;Priority;Description;Checklist\n"
        "Plan Prueba;Inicio;Tarea de prueba;usuario@empresa.com;01042026;medium;Descripcion;;Paso 1;Paso 2\n"
    )
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return str(csv_file)

@pytest.fixture
def fake_group_id():
    return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

@pytest.fixture
def fake_user_id():
    return "ffffffff-0000-1111-2222-333333333333"
```

---

## Datos en fixtures — Reglas de seguridad

Los archivos en `tests/fixtures/` deben cumplir:

- **Emails ficticios:** usar `usuario@empresa.com`, `pm@empresa.com`, `test@test.com`
- **GUIDs ficticios:** usar `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` o patrones claramente falsos
- **Nombres ficticios:** usar nombres genericos como "Usuario Prueba", "PM Test"
- **RUTs ficticios:** usar RUTs invalidos como `00000000-0` o `99999999-9`
- **Nunca:** datos reales de produccion, aunque esten "anonimizados"

---

## Requisitos de cobertura por modulo

| Modulo | Cobertura minima |
|---|---|
| `parse_csv()` | 90% |
| `resolve_email()` | 80% |
| Transformaciones de prioridad y fecha | 95% |
| `graph_request()` (logica de retry) | 80% |
| Flujos de orquestacion | 70% |
| Modo `--dry-run` | 100% (todos los paths) |

---

## pytest.ini

```ini
[pytest]
testpaths = tests
markers =
    integration: Tests que requieren credenciales reales y acceso a red
    slow: Tests que tardan mas de 5 segundos
filterwarnings =
    ignore::DeprecationWarning
```

---

## CI/CD

En el pipeline de CI (GitHub Actions):
- Se ejecutan **solo tests no marcados como `integration`** en cada PR
- Los tests de integracion se ejecutan manualmente o en schedule semanal contra el tenant de desarrollo
- Los secretos de desarrollo se almacenan como GitHub Secrets (nunca en el codigo)
