# Memoria de bits

RIF escribe directamente en `BitBuffer`. Un campo puede comenzar o terminar en
cualquier bit, sin limitarse a bytes completos.

## Cursor físico

```rif
-> put 0000 0001
-> ebit 1 0 1 0 1 0 1 0
-> emmit 4660
-> emitbits 5 3
```

La emisión normal avanza el cursor físico, consultable con `::SIZE`. `emmit`
usa `.wordsize`; `put` y `ebit` tienen anchos fijos; `emitbits` recibe valor y
ancho explícitos.

## Reescribir bits

```rif
-> readbits 0 8
-> patchbits 0 8 255
```

`readbits OFFSET WIDTH` lee un rango físico y apila su entero en el datastack.
`patchbits OFFSET WIDTH VALUE` reescribe el rango sin avanzar los cursores.
Fuera de rango falla antes de modificar el buffer.

Los anchos múltiplos de ocho respetan `.endianess`; los demás respetan
`.bitorder`.

## Padding y alineamiento

```rif
-> padding 3
-> alignement 16
```

Ambos emiten ceros y avanzan los dos cursores. `padding` agrega el ancho
exacto. `alignement N` alcanza el siguiente múltiplo de `N`. Ambos se registran
como padding en `RuleTrace`.

Las versiones virtuales avanzan solamente `::VSIZE`:

```rif
-> vpadding 8
-> valignement 32
```

## Reservas

```rif
-> reserve "header" 16
-> ldres "header" 0000000011111111
-> gtres "header"
-> dlres "header"
```

Una reserva física agrega bits en cero y conserva un rango con nombre. `ldres`
lo parchea, `gtres` lo copia al cursor y `dlres` quita el nombre sin limpiar
los bits ya emitidos.

```rif
-> vreserve "scratch" 64
```

Una reserva virtual no crea bits físicos. `resdir`, `resvdir`, `reswidth`,
`vreswidth`, `resdist` y `resvdist` consultan su metadata.

## Trazas

Cada invocación crea un `RuleTrace` con inicio, ancho y final físicos y
virtuales, además del padding de cada espacio. Una Rule padre incluye el output
de sus Rules hijas.

## API de bajo nivel

Los callers Python pueden usar directamente `BitBuffer`:

```python
query = buffer.query("header")
bits = buffer.read_bit_sequence(0, 12)
checkpoint = buffer.checkpoint()

with buffer.transaction():
    buffer.write_bits(0, 3, 2)
```

`rollback(checkpoint)` restaura almacenamiento, tamaño y regiones.
`transaction()` revierte automáticamente si su cuerpo falla. `to_bytes()`
devuelve una copia serializada y `view()` una vista viva. `BitQuery` expone el
valor entero, bits, rango y bytes cuando el rango está alineado.

`AssemblyImage.render()` genera una representación de las secciones usando la
configuración de `.sectiondef`, `.sectionend`, labels, comentarios y alineación.
