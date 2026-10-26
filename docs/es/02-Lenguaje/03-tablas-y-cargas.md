# Tablas y cargas

Una tabla tiene una fila de encabezado, una fila separadora y una o más filas
de datos:

```rif
@table registers
| name | opcode | bits |
________________________
| mov  | 1      | 32   |
________________________
| add  | 2      | 32   |
@end
```

La separación puede tener cualquier cantidad de `_`. Se requiere una
separación entre filas y cada fila debe terminar en `|` antes del salto de
línea.

## Acceso a tablas

```rif
-> $registers.name, IDENT
-> put $registers.opcode 0000
```

La primera instrucción compara el token actual con `name` y selecciona la fila.
Los accesos posteriores leen datos de esa fila.

El acceso indexado estático no consume un token MIR:

```rif
-> fits $registers.name[rax].bits
```

La columna selectora debe tener claves únicas cuando se usa como índice. Las
demás columnas pueden repetir valores. El índice se construye al primer uso.

## Cargar fuentes

```rif
@LOAD "tables.rif"
@LOAD "rules.rif"
```

`@LOAD` resuelve rutas relativas, exige la extensión `.rif`, detecta ciclos y
conserva el alcance de la declaración. Un archivo cargado puede aportar tablas
y Rules, pero no configuración raíz.

## Tablas en paquetes

Al crear un `.pack`, las fuentes cargadas quedan en el manifiesto junto con su
orden de dependencias. Un paquete precompilado guarda las filas en SQLite. Al
abrirse, RIF reconstruye la matriz y los índices perezosos.
