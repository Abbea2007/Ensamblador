"""Pruebas sin dependencias; la prueba gráfica requiere una pantalla."""
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
from simulador import CPU, EJEMPLO, ErrorCodigo, Simulador


def ejecutar(codigo):
    cpu, salida = CPU(codigo), []
    for _ in range(100):
        if cpu.detenida:
            return cpu, salida
        valor = cpu.paso()
        if valor is not None:
            salida.append(valor)
    raise AssertionError('No terminó dentro del límite de prueba')


class Pruebas(unittest.TestCase):
    def test_ejemplo(self):
        cpu, salida = ejecutar(EJEMPLO)
        self.assertEqual(salida, [3, 5, 6, 6])
        self.assertEqual(cpu.registros, dict(AX=6, BX=0, CX=0, DX=0))
        self.assertTrue(cpu.z)
        self.assertFalse(cpu.n)

    def test_aritmetica(self):
        cpu, salida = ejecutar('MOV AX, 0x10\nMOV BX, AX\nSUB AX, 18\nINC AX\nDEC BX\nCMP AX, BX\nMOV DX, 7\nPRINT AX\nPRINT BX')
        self.assertEqual(salida, [-1, 15])
        self.assertEqual(cpu.registros['DX'], 7)
        self.assertTrue(cpu.n)
        self.assertFalse(cpu.z)

    def test_saltos(self):
        _, salida = ejecutar('MOV AX, 1\nCMP AX, 0\nJZ error\nJNZ bien\nerror: PRINT 99\nbien: CMP AX, 1\nJNZ error\nJZ fin\nPRINT 98\nfin: JMP salida\nPRINT 97\nsalida: PRINT 0\nHLT\nPRINT 96')
        self.assertEqual(salida, [0])

    def test_lineas(self):
        cpu = CPU('; comentario\n\ninicio: MOV AX, 2\nDEC AX\nJNZ inicio')
        cpu.paso()
        self.assertEqual(cpu.ultima, 3)
        self.assertEqual(cpu.pc, 1)
        cpu.paso()
        cpu.paso()
        self.assertEqual(cpu.pc, 0)

    def test_finales(self):
        for codigo in ('', '; vacío', 'JMP fin\nfin:', 'HLT'):
            cpu, _ = ejecutar(codigo)
            self.assertTrue(cpu.detenida)
            self.assertIsNone(cpu.paso())

    def test_errores(self):
        for codigo in ('XYZ AX', 'MOV AX', 'MOV 1, AX', 'INC QQ', 'JMP falta',
                       'x: INC AX\nx: HLT', 'ADD AX,, 1', 'MOV AX, texto', 'HLT AX'):
            with self.subTest(codigo=codigo):
                with self.assertRaises(ErrorCodigo):
                    CPU(codigo)

    def test_interfaz_y_guardado_automatico(self):
        with tempfile.TemporaryDirectory() as temporal:
            with patch('simulador.descargas', return_value=Path(temporal)):
                app = Simulador()
            try:
                app.withdraw()
                app.update_idletasks()
                app.paso()
                self.assertEqual(app.cpu.pc, 1)
                self.assertEqual(app.editor.cget('state'), 'disabled')
                self.assertTrue(app.editor.tag_ranges('ultima'))
                self.assertTrue((app.carpeta / 'simulador.py').is_file())
                self.assertTrue((app.carpeta / 'ejemplo.asm').is_file())
                app.ejecutar()
                self.assertIsNotNone(app.timer)
                app.pausar()
                self.assertIsNone(app.timer)
                app.reiniciar()
                self.assertIsNone(app.cpu)
                self.assertEqual(app.editor.cget('state'), 'normal')
            finally:
                app.cerrar()


if __name__ == '__main__':
    unittest.main()
