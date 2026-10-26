# Implementación del soporte de variantes con contexto global compartido

## Resumen

Implementar `@SUPPORTS` y `@ASMVARIANT` para cargar archivos `<variante>.rif`, compilar sus Rules y delegar el análisis entre contextos.

Todas las variantes compartirán:

```text
STACK
TABLES
DEFINES
RULES
CONFIG
LINKER
```

La separación existirá únicamente en la pila de delegación sintáctica.

## Sintaxis

```rif
@SUPPORTS thumb

@ASMVARIANT thumb:
.MODE SWITCH
.ENTER "ARM_TO_THUMB"
.EXIT "THUMB_TO_ARM"
@END
```

El linker resolverá automáticamente:

```text
thumb -> thumb.rif
```

El archivo `thumb.rif` podrá contener únicamente palabras y Rules:

```rif
@rule ARM_TO_THUMB:
...

@rule THUMB_TO_ARM:
...

@define thumb_word
@rule MOV:
...
```

Las variantes no pueden declarar tablas, configuración, linker, stack,
soportes, otras variantes ni inclusiones.

Los archivos auxiliares del programa se incorporan desde el archivo raíz con
una única forma de inclusión:

```rif
@LOAD "table.rif"
@LOAD "rules.rif"
```

`@LOAD` solo acepta archivos `.rif`, resuelve la ruta relativa al archivo que
lo solicita, evita cargas repetidas y detecta ciclos. Los archivos incluidos
desde el programa raíz pueden aportar tablas, Rules y palabras; no pueden
crear una nueva configuración global ni una variante.

Las palabras reservadas nuevas serán MAYÚSCULAS:

```text
SUPPORTS
ASMVARIANT
END
MODE
SWITCH
ENCAPSULATE
ENTER
EXIT
```

Los nombres de variantes y Rules serán identificadores normales.

## Modelo global

Añadir:

```python
@dataclass(frozen=True)
class SupportData:
    name: str
    path: str
```

```python
@dataclass(frozen=True)
class AsmVariantData:
    name: str
    mode: str
    enter_rule: str
    exit_rule: str
    path: str
```

Registros compartidos:

```python
SUPPORTS: dict[str, SupportData]
ASM_VARIANTS: dict[str, AsmVariantData]
LOADED_SOURCES: dict[str, str]
ACTIVE_SOURCES: list[str]
```

`RuleData` recibirá también el archivo de origen para diagnósticos:

```python
source_path: str
```

Las Rules cargadas desde `thumb.rif` entrarán en el mismo `RULES` global. Dos Rules con el mismo nombre producirán error, aunque provengan de archivos diferentes.

## Carga de archivos

El procesamiento seguirá estas fases:

1. Procesar el archivo principal.
2. Registrar `SUPPORTS` y `ASMVARIANT`.
3. Resolver cada variante declarada.
4. Buscar `<nombre>.rif`:
   - En el directorio del archivo principal si `.SEARCHING == ""`.
   - En la carpeta indicada por `.SEARCHING`.
   - No buscar si `.SEARCHING == false`.
5. Canonicalizar la ruta.
6. Evitar cargar dos veces el mismo archivo.
7. Tokenizar y parsear el archivo delegado con `RIF_LANG_SESSION`.
8. Procesar sus declaraciones dentro del mismo contexto global.
9. Procesar las inclusiones explícitas `@LOAD` en su posición.
10. Validar que todas las Rules `ENTER` y `EXIT` existan.

Los archivos de variantes no podrán declarar otro `CONFIG` ni otro `LINKER`; esas configuraciones pertenecen al contexto global principal. Sí podrán aportar Rules, Defines, Tables y nuevas variantes.

## Contextos de delegación

Crear un `VariantFrame`:

```python
@dataclass
class VariantFrame:
    variant: AsmVariantData
    source_path: str
    return_rule: str | None
    token_position: int
```

El MID parser mantendrá:

```python
variant_stack: list[VariantFrame]
```

El frame no tendrá copias de Tables, Defines o Stack. Consultará directamente el contexto global.

### SWITCH

- Ejecuta `ENTER` en el contexto actual.
- Hace push de la variante.
- Las Rules siguientes se buscan en el contexto de la variante.
- Continúa hasta que coincida `EXIT`.
- Hace pop del frame.
- Retoma el contexto padre después del token consumido por `EXIT`.
- El estado de la variante se mantiene mientras dure el segmento delegado.

### ENCAPSULATE

- `ENTER` reconoce el inicio de una encapsulación sintáctica.
- El contenido se delega por completo a la variante.
- `EXIT` reconoce el cierre de la encapsulación.
- Al cerrar, el parser retorna automáticamente al contexto padre.
- La variante no conserva estado fuera del bloque encapsulado.

## API

Extender el procesador para recibir el archivo de origen:

```python
process(
    result,
    source_path=None,
    *,
    load_variants=True,
)
```

Añadir un cargador reutilizable:

```python
load_variants(
    root_path,
    context,
)
```

Y una operación de resolución:

```python
resolve_variant(
    name,
    root_path,
    linker_config,
)
```

`main.py` pasará la ruta real del archivo principal a `process`.

## Validaciones

- `@SUPPORTS` debe declarar un nombre único.
- `@ASMVARIANT` debe referirse a un `@SUPPORTS` existente.
- No se permiten variantes duplicadas.
- `.MODE` solo acepta `SWITCH` o `ENCAPSULATE`.
- `.ENTER` y `.EXIT` deben recibir Rules no vacías.
- El archivo `<variante>.rif` debe existir.
- Se detectan ciclos de carga.
- Se detectan Rules duplicadas entre archivos.
- Se detectan Rules de entrada o salida inexistentes.
- Una variante solo puede declarar `DEFINE` y `RULE`.
- Un archivo incluido no puede sobrescribir `CONFIG`, `LINKER` ni declarar variantes.
- La búsqueda de archivos respeta `.SEARCHING`.
- Se conserva el archivo de origen en todos los errores.

## Pruebas

Añadir pruebas con archivos temporales para:

- Variante simple `thumb.rif`.
- Variante `SWITCH`.
- Variante `ENCAPSULATE`.
- Rules de entrada y salida.
- Tabla declarada en el archivo principal y usada por `thumb.rif`.
- Define declarado en el archivo principal y usado por una variante.
- Stack compartido entre archivo principal y variante.
- Rules agregadas por una variante al `RULES` global.
- Dos variantes accediendo al mismo contexto.
- Inclusiones de tablas y Rules con `@LOAD`.
- Ciclos de `@LOAD`.
- Archivo inexistente.
- `.SEARCHING false`.
- `.SEARCHING ""`.
- Carpeta de búsqueda relativa al archivo principal.
- Carga duplicada del mismo archivo.
- Ciclo directo y ciclo indirecto.
- Rule duplicada entre archivos.
- Configuración duplicada desde una variante.
- Variante declarada sin soporte.
- Mode inválido.
- Entrada o salida inexistente.

Stress tests:

- 100 variantes.
- Cadena de 50 variantes anidadas.
- 1,000 Rules distribuidas entre archivos.
- Reutilización del mismo archivo por múltiples variantes.
- Tablas grandes compartidas por todas las variantes.
- Carga repetida para verificar que el caché evita reprocesamiento.

Criterios de aceptación:

```text
python -m unittest discover -v
vnma run main.py main.rif
```

deben completarse correctamente, y las pruebas deben confirmar que todas las variantes comparten exactamente las mismas instancias globales de Stack, Tables, Defines y Rules.
