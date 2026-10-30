; Suma 3 + 2 + 1
MOV AX, 0
MOV CX, 3
bucle:
    ADD AX, CX
    PRINT AX
    DEC CX
    CMP CX, 0
    JNZ bucle
PRINT AX
HLT
