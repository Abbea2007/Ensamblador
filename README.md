# Simulador educativo de ensamblador

Requiere Python 3 con Tkinter. No utiliza dependencias externas.

Desde esta carpeta, ejecutar en Windows:

```console
py simulador.py
```

En otros sistemas: `python3 simulador.py`. Tkinter debe estar incluido en la
instalación de Python (algunas distribuciones Linux lo distribuyen por separado).

## Demostración

1. Pulsar **Paso (F7)** para ejecutar una instrucción.
2. Observar los registros que cambian en verde claro. La línea ejecutada queda
   verde y la siguiente, ámbar. Si ambas coinciden, prevalece el ámbar.
3. Seguir hasta `JNZ bucle` para observar el salto del PC.
4. **Ejecutar (F5)** continúa con el intervalo indicado. **Pausar** permite parar,
   incluso dentro de un bucle infinito.
5. El ejemplo imprime `3`, `5`, `6`, `6` y termina con AX=6, CX=0, Z=1, N=0.
6. **Reiniciar / editar** limpia CPU y consola, conserva el código y desbloquea
   el editor. Durante la simulación el código permanece bloqueado.

## Modelo

AX, BX, CX y DX contienen enteros sin límite fijo de bits. PC es el índice de la
siguiente instrucción desde 0: no cuenta etiquetas, comentarios ni líneas vacías.
Después de HLT apunta a la posición siguiente, pero no la ejecuta.
Z indica resultado cero y N resultado negativo; ambas empiezan en 0.
No se emulan memoria, ciclos, acarreo ni desbordamiento de una CPU real.

| Instrucción | Efecto |
| --- | --- |
| MOV AX, 5 | Copia un valor o registro |
| ADD AX, BX | Suma al registro destino |
| SUB AX, 2 | Resta al registro destino |
| INC AX / DEC AX | Incrementa / decrementa uno |
| CMP AX, 0 | Actualiza banderas de AX−0 sin modificar registros |
| JMP etiqueta | Salta siempre |
| JZ etiqueta | Salta si Z=1 |
| JNZ etiqueta | Salta si Z=0 |
| PRINT AX | Imprime un registro o número |
| HLT | Termina |

ADD, SUB, INC, DEC y CMP actualizan Z y N; las demás las conservan. Se aceptan
decimales con signo y hexadecimales como `0x10`. Separar operandos con coma.
Mayúsculas y minúsculas son equivalentes. Los comentarios comienzan con `;`.
Las etiquetas usan letras ASCII, números y `_`, sin empezar por número. Pueden
estar solas o antes de una instrucción. También se termina al alcanzar el final.
Los errores de sintaxis se indican con su línea antes de ejecutar el programa.

## Guardado automático

Al iniciar se detecta Descargas mediante la carpeta conocida de Windows o XDG
en Linux, con Downloads/Descargas como alternativa. Se crea la subcarpeta
`Simulador_Ensamblador`, se copia allí el código fuente y se crea `ejemplo.asm`
si no existe. Si ya había otra versión del fuente, se conserva una copia en
`simulador_anterior.py` antes de actualizarlo. **Guardar .asm (Ctrl+S)** permite
guardar el editor en esa ubicación o elegir otra. Los errores de permisos se
muestran sin impedir el uso del programa.

El intérprete `CPU` está separado de la ventana `Simulador` para facilitar la
explicación y las pruebas. La ejecución usa `after` de Tkinter para mantener
la interfaz disponible entre instrucciones.

Pruebas del intérprete y prueba básica de la ventana:

```console
py -m unittest -v test_simulador.py
```
