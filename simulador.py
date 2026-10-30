"""Simulador educativo sin dependencias. Ejecutar: py simulador.py"""
import ctypes
import os
from pathlib import Path
import re
import shutil
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

EJEMPLO = """; Sumar 3 + 2 + 1. Resultado: AX = 6
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
"""


def descargas():
    """Respeta carpetas redirigidas de Windows y la configuración XDG."""
    home = Path.home()
    if os.name == 'nt':
        import uuid
        class GUID(ctypes.Structure):
            _fields_ = [('data', ctypes.c_byte * 16)]
        guid = GUID.from_buffer_copy(uuid.UUID('374de290-123f-4565-9164-39c4925e467b').bytes_le)
        ruta = ctypes.c_wchar_p()
        funcion = ctypes.windll.shell32.SHGetKnownFolderPath
        funcion.argtypes = [ctypes.POINTER(GUID), ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
        funcion.restype = ctypes.c_long
        if funcion(ctypes.byref(guid), 0, None, ctypes.byref(ruta)) == 0:
            try:
                return Path(ruta.value)
            finally:
                ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(ruta, ctypes.c_void_p))
    elif sys.platform.startswith('linux'):
        config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
        try:
            texto = (config / 'user-dirs.dirs').read_text(encoding='utf-8')
            match = re.search(r'^XDG_DOWNLOAD_DIR="([^"]+)"', texto, re.M)
            if match:
                ruta = Path(match[1].replace('${HOME}', str(home)).replace('$HOME', str(home)))
                if ruta.is_absolute():
                    return ruta
        except OSError:
            pass
    for nombre in ('Downloads', 'Descargas'):
        if (home / nombre).is_dir():
            return home / nombre
    return home / 'Downloads'


class ErrorCodigo(ValueError):
    def __init__(self, linea, mensaje):
        self.linea = linea
        super().__init__(f'Línea {linea}: {mensaje}')


class CPU:
    """Enteros sin límite fijo de bits; PC indexa instrucciones desde cero.

    ADD/SUB/INC/DEC/CMP actualizan Z y N. Las demás conservan las banderas.
    CMP calcula una resta sin modificar registros.
    """
    NOMBRES = ('AX', 'BX', 'CX', 'DX')
    ARIDAD = dict(MOV=2, ADD=2, SUB=2, INC=1, DEC=1, CMP=2,
                  JMP=1, JZ=1, JNZ=1, PRINT=1, HLT=0)

    def __init__(self, texto):
        self.registros = dict.fromkeys(self.NOMBRES, 0)
        self.pc = 0
        self.z = self.n = False
        self.ultima = None
        self.programa, self.etiquetas = [], {}
        for linea, texto in enumerate(texto.splitlines(), 1):
            texto = texto.split(';', 1)[0].strip().upper()
            if not texto:
                continue
            if ':' in texto:
                etiqueta, texto = texto.split(':', 1)
                etiqueta, texto = etiqueta.strip(), texto.strip()
                if not re.fullmatch(r'[A-Z_][A-Z_0-9]*', etiqueta):
                    raise ErrorCodigo(linea, 'etiqueta inválida')
                if etiqueta in self.etiquetas:
                    raise ErrorCodigo(linea, 'etiqueta duplicada')
                self.etiquetas[etiqueta] = len(self.programa)
                if not texto:
                    continue
            partes = texto.split(None, 1)
            op = partes[0]
            args = [x.strip() for x in partes[1].split(',')] if len(partes) == 2 else []
            if op not in self.ARIDAD:
                raise ErrorCodigo(linea, f'instrucción desconocida: {op}')
            if len(args) != self.ARIDAD[op] or any(not a for a in args):
                raise ErrorCodigo(linea, f'{op} requiere {self.ARIDAD[op]} operandos separados por coma')
            self.programa.append((linea, op, args))
        for linea, op, args in self.programa:
            if op in ('JMP', 'JZ', 'JNZ'):
                if args[0] not in self.etiquetas:
                    raise ErrorCodigo(linea, f'etiqueta inexistente: {args[0]}')
                continue
            if op in ('MOV', 'ADD', 'SUB', 'INC', 'DEC') and args[0] not in self.registros:
                raise ErrorCodigo(linea, 'el destino debe ser AX, BX, CX o DX')
            for arg in args:
                try:
                    self.valor(arg)
                except ValueError:
                    raise ErrorCodigo(linea, f'operando inválido: {arg}') from None
        self.detenida = not self.programa

    def valor(self, arg):
        if arg in self.registros:
            return self.registros[arg]
        if re.fullmatch(r'[+-]?[0-9]+', arg):
            return int(arg, 10)
        if re.fullmatch(r'[+-]?0X[0-9A-F]+', arg):
            return int(arg, 16)
        raise ValueError('Se esperaba registro o entero')

    def paso(self):
        if self.detenida:
            return None
        self.ultima, op, args = self.programa[self.pc]
        siguiente, resultado, salida = self.pc + 1, None, None
        if op == 'MOV':
            self.registros[args[0]] = self.valor(args[1])
        elif op in ('ADD', 'SUB', 'INC', 'DEC'):
            cantidad = self.valor(args[1]) if len(args) == 2 else 1
            signo = 1 if op in ('ADD', 'INC') else -1
            resultado = self.registros[args[0]] + signo * cantidad
            self.registros[args[0]] = resultado
        elif op == 'CMP':
            resultado = self.valor(args[0]) - self.valor(args[1])
        elif op in ('JMP', 'JZ', 'JNZ'):
            if op == 'JMP' or (op == 'JZ' and self.z) or (op == 'JNZ' and not self.z):
                siguiente = self.etiquetas[args[0]]
        elif op == 'PRINT':
            salida = self.valor(args[0])
        elif op == 'HLT':
            self.detenida = True
        if resultado is not None:
            self.z, self.n = resultado == 0, resultado < 0
        self.pc = siguiente
        self.detenida = self.detenida or self.pc >= len(self.programa)
        return salida


class Simulador(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Laboratorio de ensamblador')
        self.geometry('1060x740')
        self.minsize(900, 680)
        self.cpu, self.timer = None, None
        self.corriendo, self.pasos = False, 0
        self.carpeta = None
        aviso = None
        try:
            self.carpeta = descargas() / 'Simulador_Ensamblador'
            self.carpeta.mkdir(parents=True, exist_ok=True)
            origen, destino = Path(__file__).resolve(), self.carpeta / 'simulador.py'
            if origen != destino.resolve():
                if destino.exists() and destino.read_bytes() != origen.read_bytes():
                    shutil.copy2(destino, self.carpeta / 'simulador_anterior.py')
                shutil.copy2(origen, destino)
            ejemplo = self.carpeta / 'ejemplo.asm'
            if not ejemplo.exists():
                ejemplo.write_text(EJEMPLO, encoding='utf-8')
        except OSError as exc:
            aviso = f'No se pudo preparar Descargas: {exc}. Puedes elegir otra carpeta al guardar.'
        self.crear_interfaz()
        self.editor.insert('1.0', EJEMPLO)
        self.reiniciar()
        self.bind('<F7>', lambda e: self.paso())
        self.bind('<F5>', lambda e: self.ejecutar())
        self.bind('<Control-s>', lambda e: self.guardar())
        self.protocol('WM_DELETE_WINDOW', self.cerrar)
        if aviso:
            self.after_idle(lambda: messagebox.showwarning('Guardado', aviso))

    def crear_interfaz(self):
        estilo = ttk.Style(self)
        estilo.theme_use('clam')
        estilo.configure('TButton', font=('Segoe UI', 10), padding=8)
        estilo.configure('TLabel', font=('Segoe UI', 10))
        base = ttk.Frame(self, padding=16)
        base.pack(fill='both', expand=True)
        ttk.Label(base, text='Laboratorio de ensamblador', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(base, text='Escribe, ejecuta y observa cómo cambia la CPU.').pack(anchor='w', pady=(0, 12))
        barra = ttk.Frame(base)
        barra.pack(fill='x', pady=(0, 12))
        self.botones = {}
        for nombre, accion in [('Paso · F7', self.paso), ('Ejecutar · F5', self.ejecutar),
                ('Pausar', self.pausar), ('Reiniciar / editar', self.reiniciar),
                ('Guardar .asm', self.guardar), ('Abrir .asm', self.abrir)]:
            boton = ttk.Button(barra, text=nombre, command=accion)
            boton.pack(side='left', padx=(0, 5))
            self.botones[nombre] = boton
        cuerpo = ttk.Frame(base)
        cuerpo.pack(fill='both', expand=True)
        cuerpo.columnconfigure(0, weight=3)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        panel = ttk.LabelFrame(cuerpo, text='Código ensamblador', padding=8)
        panel.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        contenedor = ttk.Frame(panel)
        contenedor.pack(fill='both', expand=True)
        self.editor = tk.Text(contenedor, width=55, height=16, bg='#182333', fg='#e6edf5',
            insertbackground='white', font=('Consolas', 12), padx=12, pady=10, undo=True, wrap='none')
        sy = ttk.Scrollbar(contenedor, command=self.editor.yview)
        sx = ttk.Scrollbar(panel, orient='horizontal', command=self.editor.xview)
        self.editor.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side='right', fill='y')
        self.editor.pack(fill='both', expand=True)
        sx.pack(fill='x')
        for tag, color in [('ultima', '#246149'), ('siguiente', '#705922'), ('error', '#a33039')]:
            self.editor.tag_configure(tag, background=color, foreground='white')
        ttk.Label(panel, text='Verde: ejecutada • Ámbar: siguiente • Rojo: error').pack(anchor='w', pady=8)
        lateral = ttk.LabelFrame(cuerpo, text='Estado de la CPU', padding=12)
        lateral.grid(row=0, column=1, sticky='nsew')
        self.valores = {}
        for nombre in (*CPU.NOMBRES, 'PC', 'Z', 'N'):
            fila = ttk.Frame(lateral)
            fila.pack(fill='x', pady=3)
            ttk.Label(fila, text=nombre, width=4, font=('Consolas', 13, 'bold')).pack(side='left')
            label = tk.Label(fila, text='0', anchor='e', bg='white', font=('Consolas', 13), padx=8)
            label.pack(side='right', fill='x', expand=True)
            self.valores[nombre] = label
        ttk.Label(lateral, text='PC: índice desde 0\nZ: resultado cero\nN: resultado negativo').pack(anchor='w', pady=10)
        ttk.Label(lateral, text='Intervalo entre pasos (ms)').pack(anchor='w')
        self.demora = tk.IntVar(value=350)
        ttk.Spinbox(lateral, from_=20, to=2000, increment=50, textvariable=self.demora, width=10).pack(anchor='w', pady=5)
        ttk.Button(lateral, text='Guía de instrucciones', command=self.ayuda).pack(fill='x', pady=8)
        consola = ttk.LabelFrame(base, text='Consola · PRINT', padding=8)
        consola.pack(fill='x', pady=10)
        self.consola = tk.Text(consola, height=5, state='disabled', font=('Consolas', 11), wrap='word')
        scroll = ttk.Scrollbar(consola, command=self.consola.yview)
        self.consola.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.consola.pack(fill='x')
        self.estado = tk.StringVar()
        ttk.Label(base, textvariable=self.estado, wraplength=990).pack(anchor='w')
        ttk.Label(base, text=f'Guardado: {self.carpeta or "elige una carpeta al guardar"}', wraplength=990).pack(anchor='w', pady=4)

    def actualizar(self):
        datos = dict.fromkeys((*CPU.NOMBRES, 'PC', 'Z', 'N'), 0)
        if self.cpu:
            datos.update(self.cpu.registros)
            datos.update(PC=self.cpu.pc, Z=int(self.cpu.z), N=int(self.cpu.n))
        for nombre, valor in datos.items():
            label = self.valores[nombre]
            cambio = str(label.cget('text')) != str(valor)
            label.configure(text=str(valor), bg='#c6f0db' if cambio else 'white')
        final = self.cpu is not None and self.cpu.detenida
        for nombre in ('Paso · F7', 'Ejecutar · F5'):
            self.botones[nombre].configure(state='disabled' if self.corriendo or final else 'normal')
        self.botones['Pausar'].configure(state='normal' if self.corriendo else 'disabled')
        for tag in ('ultima', 'siguiente', 'error'):
            self.editor.tag_remove(tag, '1.0', 'end')
        if self.cpu:
            if self.cpu.ultima:
                linea = self.cpu.ultima
                self.editor.tag_add('ultima', f'{linea}.0', f'{linea}.end+1c')
            if not final:
                linea = self.cpu.programa[self.cpu.pc][0]
                self.editor.tag_add('siguiente', f'{linea}.0', f'{linea}.end+1c')
                self.editor.see(f'{linea}.0')

    def preparar(self):
        if self.cpu is not None:
            return True
        try:
            self.cpu = CPU(self.editor.get('1.0', 'end-1c'))
        except ErrorCodigo as exc:
            self.actualizar()
            self.editor.tag_add('error', f'{exc.linea}.0', f'{exc.linea}.end+1c')
            self.editor.see(f'{exc.linea}.0')
            self.estado.set(str(exc))
            return False
        self.editor.configure(state='disabled')
        return True

    def avanzar(self):
        if not self.cpu.detenida:
            salida = self.cpu.paso()
            self.pasos += 1
            if salida is not None:
                self.consola.configure(state='normal')
                self.consola.insert('end', str(salida) + '\n')
                self.consola.see('end')
                self.consola.configure(state='disabled')
        if self.cpu.detenida:
            self.corriendo = False
            self.estado.set(f'Finalizado · {self.pasos} instrucciones. Reinicia para editar o repetir.')
        else:
            siguiente = self.cpu.programa[self.cpu.pc][0]
            self.estado.set(f'Ejecutada: línea {self.cpu.ultima} · Siguiente: línea {siguiente} · Pasos: {self.pasos}')
        self.actualizar()

    def paso(self):
        if not self.corriendo and self.preparar():
            self.avanzar()

    def ejecutar(self):
        if self.corriendo or not self.preparar():
            return
        self.corriendo = True
        self.continuar()

    def continuar(self):
        self.timer = None
        if not self.corriendo:
            return
        self.avanzar()
        if self.corriendo:
            try:
                demora = max(20, min(2000, self.demora.get()))
            except (ValueError, tk.TclError):
                demora = 350
            # Cada paso devuelve el control a Tkinter: un bucle se puede pausar.
            self.timer = self.after(demora, self.continuar)

    def pausar(self):
        self.corriendo = False
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        self.estado.set('En pausa. Continúa con Paso o Ejecutar; reinicia para editar.')
        self.actualizar()

    def reiniciar(self):
        self.pausar()
        self.cpu, self.pasos = None, 0
        self.editor.configure(state='normal')
        self.consola.configure(state='normal')
        self.consola.delete('1.0', 'end')
        self.consola.configure(state='disabled')
        self.actualizar()
        self.estado.set('Listo para editar. Paso ejecuta una instrucción; Ejecutar recorre el programa.')

    def guardar(self):
        ruta = filedialog.asksaveasfilename(initialdir=str(self.carpeta or Path.home()),
            initialfile='programa.asm', defaultextension='.asm', filetypes=[('Ensamblador', '*.asm'), ('Texto', '*.txt')])
        if ruta:
            try:
                Path(ruta).write_text(self.editor.get('1.0', 'end-1c'), encoding='utf-8')
                self.estado.set(f'Guardado: {ruta}')
            except OSError as exc:
                messagebox.showerror('No se pudo guardar', str(exc))

    def abrir(self):
        self.pausar()
        ruta = filedialog.askopenfilename(initialdir=str(self.carpeta or Path.home()),
            filetypes=[('Ensamblador', '*.asm'), ('Texto', '*.txt'), ('Todos', '*.*')])
        if not ruta:
            return
        try:
            codigo = Path(ruta).read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError) as exc:
            messagebox.showerror('No se pudo abrir', str(exc))
            return
        if self.editor.get('1.0', 'end-1c').strip() and not messagebox.askyesno(
                'Reemplazar código', 'Se reemplazará el contenido del editor. ¿Continuar?'):
            return
        self.reiniciar()
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', codigo)
        self.editor.edit_reset()

    def ayuda(self):
        messagebox.showinfo('Guía rápida', 'MOV AX, 5: copia un valor o registro\n'
            'ADD AX, BX / SUB AX, 2: suma / resta\nINC AX / DEC AX: incrementa / decrementa\n'
            'CMP AX, 0: compara sin modificar los registros\nJMP etiqueta: salta siempre\n'
            'JZ etiqueta: salta si Z=1\nJNZ etiqueta: salta si Z=0\nPRINT AX: imprime un valor\nHLT: termina\n\n'
            'ADD, SUB, INC, DEC y CMP actualizan Z y N.\nLas demás conservan las banderas.\n'
            'PC cuenta instrucciones desde 0, no líneas del editor.\n'
            'Etiquetas: bucle: (solas o antes de una instrucción).\nComentarios: ; texto. Mayúsculas indistintas.\n'
            'Números: decimales con signo y hexadecimales (0x10).\n'
            'Modelo sin memoria, acarreo ni desbordamiento.\nTambién se termina al llegar al final del código.\n'
            'Reiniciar conserva el código y permite editarlo.')

    def cerrar(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
        self.destroy()


if __name__ == '__main__':
    Simulador().mainloop()
