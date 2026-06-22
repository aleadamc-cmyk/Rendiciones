#!/usr/bin/env python3
"""
Generador de Manual de Usuario PDF - HGT Rendiciones de Gastos
Ejecutar: python generate_manual.py
Salida: Manual_Usuario_HGT_Rendiciones.pdf
"""

from fpdf import FPDF
import os

# ── Colores HGT ────────────────────────────────────────────────────────
HGT_ORANGE = (249, 115, 22)
HGT_BLUE = (30, 58, 95)
HGT_DARK = (33, 42, 55)
HGT_LIGHT_BG = (248, 250, 252)
HGT_WHITE = (255, 255, 255)
HGT_GRAY = (107, 114, 128)
HGT_GREEN = (22, 163, 74)
HGT_RED = (185, 28, 28)
TABLE_HEADER_BG = (30, 58, 95)
TABLE_ALT_ROW = (248, 250, 252)
BORDER_COLOR = (209, 213, 219)


class ManualPDF(FPDF):
    def __init__(self):
        super().__init__('P', 'mm', 'Letter')
        self.chapter_num = 0
        self.chapter_titles = []
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(*HGT_GRAY)
        self.cell(0, 6, 'Manual de Usuario - HGT Rendiciones de Gastos', 0, 0, 'L')
        self.cell(0, 6, f'Pagina {self.page_no()}', 0, 1, 'R')
        self.set_draw_color(*HGT_ORANGE)
        self.set_line_width(0.5)
        self.line(10, 14, self.w - 10, 14)
        self.ln(8)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-20)
        self.set_draw_color(*BORDER_COLOR)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(3)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*HGT_GRAY)
        self.cell(0, 5, 'HGT Chile Logistics - Sistema de Rendiciones de Gastos', 0, 0, 'L')
        self.cell(0, 5, 'Confidencial', 0, 0, 'R')

    def chapter_title(self, title):
        self.chapter_num += 1
        self.chapter_titles.append((self.chapter_num, title, self.page_no()))
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(*HGT_BLUE)
        self.cell(0, 12, f'{self.chapter_num}. {title}', 0, 1, 'L')
        self.set_draw_color(*HGT_ORANGE)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(6)

    def section_title(self, title):
        self.ln(3)
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(*HGT_BLUE)
        self.cell(0, 8, title, 0, 1, 'L')
        self.ln(2)

    def subsection_title(self, title):
        self.ln(2)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(*HGT_DARK)
        self.cell(0, 7, title, 0, 1, 'L')
        self.ln(1)

    def body_text(self, text):
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*HGT_DARK)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def bullet(self, text, indent=15):
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*HGT_DARK)
        x = self.get_x()
        self.cell(indent, 5, '')
        self.set_font('Helvetica', 'B', 9)
        self.cell(4, 5, '-')
        self.set_font('Helvetica', '', 9)
        self.multi_cell(0, 5, f'  {text}')
        self.ln(1)

    def note_box(self, text, title='Nota'):
        self.ln(2)
        self.set_fill_color(255, 251, 235)
        self.set_draw_color(*HGT_ORANGE)
        self.set_line_width(0.4)
        y_start = self.get_y()
        self.rect(12, y_start, self.w - 24, 16, 'DF')
        self.set_xy(16, y_start + 2)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(*HGT_ORANGE)
        self.cell(0, 5, f'{title}:', 0, 1)
        self.set_x(16)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(*HGT_DARK)
        self.multi_cell(self.w - 32, 4, text)
        self.set_y(y_start + 18)

    def info_box(self, text, title='Importante'):
        self.ln(2)
        self.set_fill_color(239, 246, 255)
        self.set_draw_color(59, 130, 246)
        self.set_line_width(0.4)
        y_start = self.get_y()
        self.rect(12, y_start, self.w - 24, 16, 'DF')
        self.set_xy(16, y_start + 2)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(59, 130, 246)
        self.cell(0, 5, f'{title}:', 0, 1)
        self.set_x(16)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(*HGT_DARK)
        self.multi_cell(self.w - 32, 4, text)
        self.set_y(y_start + 18)

    def simple_table(self, headers, data, col_widths=None):
        if col_widths is None:
            col_widths = [(self.w - 20) / len(headers)] * len(headers)
        # Header
        self.set_font('Helvetica', 'B', 8)
        self.set_fill_color(*TABLE_HEADER_BG)
        self.set_text_color(*HGT_WHITE)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, 1, 0, 'C', True)
        self.ln()
        # Rows
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*HGT_DARK)
        for row_idx, row in enumerate(data):
            if row_idx % 2 == 1:
                self.set_fill_color(*TABLE_ALT_ROW)
                fill = True
            else:
                self.set_fill_color(*HGT_WHITE)
                fill = True
            max_h = 7
            for i, cell in enumerate(row):
                self.cell(col_widths[i], max_h, str(cell), 1, 0, 'L', fill)
            self.ln()
        self.ln(3)

    def step(self, number, text):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(*HGT_ORANGE)
        self.cell(8, 5, f'{number}.')
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*HGT_DARK)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def add_page_break(self):
        self.add_page()


# ══════════════════════════════════════════════════════════════════════
# PORTADA
# ══════════════════════════════════════════════════════════════════════

def portada(pdf):
    pdf.add_page()
    pdf.ln(50)
    # Logo text
    pdf.set_font('Helvetica', 'B', 42)
    pdf.set_text_color(*HGT_ORANGE)
    pdf.cell(0, 18, 'HGT', 0, 1, 'C')
    pdf.set_font('Helvetica', '', 14)
    pdf.set_text_color(*HGT_BLUE)
    pdf.cell(0, 8, 'Chile Logistics', 0, 1, 'C')
    pdf.ln(10)
    # Title
    pdf.set_draw_color(*HGT_ORANGE)
    pdf.set_line_width(1.5)
    pdf.line(60, pdf.get_y(), pdf.w - 60, pdf.get_y())
    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_text_color(*HGT_BLUE)
    pdf.cell(0, 12, 'Manual de Usuario', 0, 1, 'C')
    pdf.ln(3)
    pdf.set_font('Helvetica', '', 16)
    pdf.set_text_color(*HGT_DARK)
    pdf.cell(0, 10, 'Sistema de Rendiciones de Gastos', 0, 1, 'C')
    pdf.ln(8)
    pdf.set_draw_color(*HGT_ORANGE)
    pdf.set_line_width(1.5)
    pdf.line(60, pdf.get_y(), pdf.w - 60, pdf.get_y())
    pdf.ln(15)
    # Info
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(*HGT_GRAY)
    pdf.cell(0, 7, 'Version 2.0 - Junio 2026', 0, 1, 'C')
    pdf.cell(0, 7, 'Todos los roles: Usuario, Jefatura, Encargado, Admin', 0, 1, 'C')
    pdf.ln(30)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(*HGT_GRAY)
    pdf.cell(0, 5, 'Documento confidencial - Uso interno HGT Chile Logistics', 0, 1, 'C')


# ══════════════════════════════════════════════════════════════════════
# INDICE
# ══════════════════════════════════════════════════════════════════════

def indice(pdf):
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(*HGT_BLUE)
    pdf.cell(0, 12, 'Indice de Contenidos', 0, 1, 'L')
    pdf.set_draw_color(*HGT_ORANGE)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 70, pdf.get_y())
    pdf.ln(8)
    chapters = [
        ('Introduccion', 'Que es este manual, para que sirve el sistema'),
        ('Acceso al Sistema', 'Login, roles, permisos, sesion'),
        ('Crear Rendicion', 'Formulario completo paso a paso'),
        ('Mis Rendiciones', 'Historial, estados, ver PDF'),
        ('Aprobacion (Jefatura)', 'Panel de aprobaciones, aprobar/rechazar'),
        ('Panel Encargado', 'KPIs, filtrar, tomar, procesar rendiciones'),
        ('Resumen Ejecutivo', 'Dashboard, filtros, exportar Excel'),
        ('Gestion de Usuarios', 'CRUD, roles, centros de costo'),
        ('Mantencion de Datos', 'Trayectos, jefaturas, cuentas, CC'),
        ('Referencia Tecnica', 'Workflow, calculos, IA, seguridad'),
    ]
    for i, (title, desc) in enumerate(chapters, 1):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(*HGT_BLUE)
        pdf.cell(8, 7, f'{i}.')
        pdf.cell(60, 7, title)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(*HGT_GRAY)
        pdf.cell(0, 7, f'- {desc}', 0, 1)
        pdf.ln(1)


# ══════════════════════════════════════════════════════════════════════
# CAP 1: INTRODUCCION
# ══════════════════════════════════════════════════════════════════════

def cap_introduccion(pdf):
    pdf.add_page()
    pdf.chapter_title('Introduccion')
    pdf.section_title('1.1 Que es este manual')
    pdf.body_text(
        'Este manual describe como utilizar el Sistema de Rendiciones de Gastos de HGT Chile Logistics. '
        'Explica cada funcion disponible segun el rol del usuario, con instrucciones paso a paso '
        'y una referencia tecnica completa.'
    )
    pdf.section_title('1.2 Para que sirve el sistema')
    pdf.body_text(
        'El sistema permite a los funcionarios de HGT registrar gastos de viaje de trabajo '
        '(comisiones de servicios), adjuntar documentos de respaldo, y someterlos a un flujo '
        'de aprobacion jerarquico: primero por el jefe directo (Jefatura) y luego por el '
        'Encargado de_area. El sistema genera automaticamente el PDF de la rendicion, '
        'calcula costos vehiculares, y envia notificaciones por email.'
    )
    pdf.section_title('1.3 Flujo general del proceso')
    pdf.body_text('El ciclo de vida de una rendicion de gastos es:')
    pdf.bullet('El funcionario crea la rendicion con todos sus gastos y documentos de respaldo.')
    pdf.bullet('La rendicion se envia por email al Jefe Directo (Jefatura) para revision.')
    pdf.bullet('La Jefatura aprueba (con confirmacion de RUT) o rechaza la rendicion.')
    pdf.bullet('El Encargado revisa, corrige cuentas contables si es necesario, y procesa finalmente.')
    pdf.bullet('Se genera el PDF final y se notifica al funcionario por email con el documento adjunto.')
    pdf.section_title('1.4 Roles del sistema')
    pdf.simple_table(
        ['Rol', 'Descripcion', 'Permisos principales'],
        [
            ['Usuario', 'Funcionario que rinde gastos', 'Crear rendiciones, ver historial, ver PDF'],
            ['Jefatura', 'Jefe directo del funcionario', 'Aprobar/rechazar rendiciones asignadas'],
            ['Encargado', 'Ultimo nivel de aprobacion', 'Procesar, editar cuentas, dashboard'],
            ['Admin', 'Administrador del sistema', 'Gestionar usuarios, mantencion de datos'],
            ['Super Admin', 'Super usuario', 'Todos los permisos, no se puede editar'],
        ],
        [35, 55, 95]
    )
    pdf.section_title('1.5 Stack tecnologico')
    pdf.simple_table(
        ['Componente', 'Tecnologia'],
        [
            ['Backend', 'Python Flask'],
            ['Base de datos', 'SQLite (rendiciones_hgt.db)'],
            ['Frontend', 'HTML5, CSS3, JavaScript (Jinja2)'],
            ['Componentes UI', 'TomSelect, DataTables, Font Awesome'],
            ['IA / OCR', 'Google Gemini (gemini-2.5-flash)'],
            ['PDF', 'fpdf2 + qrcode'],
            ['Email', 'SMTP con TLS (Gmail)'],
        ],
        [50, 130]
    )


# ══════════════════════════════════════════════════════════════════════
# CAP 2: ACCESO AL SISTEMA
# ══════════════════════════════════════════════════════════════════════

def cap_acceso(pdf):
    pdf.add_page()
    pdf.chapter_title('Acceso al Sistema')
    pdf.section_title('2.1 Iniciar sesion')
    pdf.body_text('Para acceder al sistema, abra el navegador e ingrese la URL asignada por el administrador.')
    pdf.step(1, 'Ingrese su nombre de usuario o nombre completo en el campo "Usuario".')
    pdf.step(2, 'Ingrese su contrasena en el campo "Contrasena". Puede hacer clic en el icono de ojo para mostrarla.')
    pdf.step(3, 'Haga clic en el boton "Iniciar Sesion".')
    pdf.note_box('Si los datos son incorrectos, el sistema mostrara "Credenciales invalidas" con un delay de 1 segundo por seguridad.')
    pdf.section_title('2.2 Cerrar sesion')
    pdf.body_text(
        'Para cerrar sesion, haga clic en su nombre de usuario en la esquina superior derecha '
        'y seleccione "Cerrar Sesion". Esto limpiara la sesion y lo redirigira al login.'
    )
    pdf.section_title('2.3 Permisos por rol')
    pdf.body_text('Segun su rol, tendra acceso a diferentes secciones del sistema:')
    pdf.simple_table(
        ['Seccion', 'Usuario', 'Jefatura', 'Encargado', 'Admin'],
        [
            ['Crear rendiciones', 'Si', 'No', 'No', 'Si'],
            ['Ver mis rendiciones', 'Si', 'No', 'No', 'Si'],
            ['Aprobar rendiciones', 'No', 'Si', 'No', 'Si'],
            ['Panel Encargado', 'No', 'No', 'Si', 'Si'],
            ['Resumen Ejecutivo', 'No', 'No', 'Si', 'Si'],
            ['Gestionar usuarios', 'No', 'No', 'No', 'Si'],
            ['Mantencion datos', 'No', 'No', 'No', 'Si'],
        ],
        [45, 28, 28, 30, 28]
    )
    pdf.section_title('2.4 Navegacion')
    pdf.body_text(
        'El sistema cuenta con un menu lateral (sidebar) en el lado izquierdo de la pantalla. '
        'En dispositivos moviles, el menu se oculta y se accede con el icono de hamburguesa '
        'en la parte superior. El contenido se carga de forma dinamica (SPA) para una '
        'experiencia mas fluida.'
    )


# ══════════════════════════════════════════════════════════════════════
# CAP 3: CREAR RENDICION
# ══════════════════════════════════════════════════════════════════════

def cap_crear_rendicion(pdf):
    pdf.add_page()
    pdf.chapter_title('Crear Rendicion')
    pdf.body_text(
        'Desde el menu lateral, seleccione "Rendiciones" para acceder al formulario de creacion. '
        'El formulario tiene 5 secciones que deben completarse en orden.'
    )

    # Seccion 1
    pdf.section_title('3.1 Seccion 1: Datos del Funcionario')
    pdf.body_text('Esta seccion se carga automaticamente con sus datos personales.')
    pdf.simple_table(
        ['Campo', 'Descripcion', 'Editable'],
        [
            ['Nombre', 'Su nombre completo (cargado del perfil)', 'No'],
            ['RUT', 'Su numero de RUT', 'Si'],
            ['Moneda', 'CLP (Pesos Chilenos) o USD (Dolares)', 'Si'],
            ['Centro de Costo', 'Centro asignado (filtrado por su perfil)', 'Si (buscable)'],
            ['Email', 'Su email corporativo', 'No'],
        ],
        [40, 90, 30]
    )
    pdf.note_box('El Centro de Costo solo muestra los centros que le fueron asignados por el administrador.')

    # Seccion 2
    pdf.section_title('3.2 Seccion 2: Comision de Servicios')
    pdf.body_text(
        'Registra los detalles de su viaje de trabajo. Puede agregar multiples filas '
        'haciendo clic en el boton "+ Agregar fila".'
    )
    pdf.simple_table(
        ['Campo', 'Descripcion', 'Valores'],
        [
            ['Traslado', 'Tipo de transporte', 'Uber / Vehiculo propio'],
            ['Desde oficina', 'Oficina de origen', 'Placilla / Renca / San Antonio / Santiago'],
            ['A localidad', 'Destino del viaje', 'Placilla / Renca / San Antonio / Santiago'],
            ['Fecha Inicio', 'Fecha de inicio del viaje', 'Formato: YYYY-MM-DD'],
            ['Fecha Termino', 'Fecha de fin del viaje', 'Formato: YYYY-MM-DD'],
            ['N personas', 'Numero de acompanantes (0-20)', 'Numero entero'],
            ['Nombres', 'Nombres de acompanantes', 'Separados por coma'],
        ],
        [35, 70, 70]
    )
    pdf.info_box(
        'Si selecciona "Vehiculo propio", el sistema calcula automaticamente el costo del '
        'traslado (km x 2 x factor), peajes y acompanantes (20% por persona). Estos costos '
        'aparecen en la seccion de Otros Gastos.'
    )

    # Seccion 3
    pdf.section_title('3.3 Seccion 3: Anticipo')
    pdf.body_text('Registra el anticipo que recibio para el viaje.')
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Fecha Egreso', 'Fecha en que se entrego el anticipo'],
            ['Monto Anticipo', 'Monto en la moneda seleccionada (CLP o USD)'],
        ],
        [50, 130]
    )

    # Seccion 4
    pdf.section_title('3.4 Seccion 4: Gastos')
    pdf.body_text(
        'Registra todos sus gastos del viaje. Use el selector "Tipo de Gasto" para cambiar '
        'entre las categorias: Alimentacion, Alojamiento y Otros.'
    )
    pdf.subsection_title('4a. Alimentacion')
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Detalle', 'Descripcion del gasto (ej: "Almuerzo cliente X")'],
            ['Tipo', 'Desayuno / Almuerzo / Cena / Otros'],
            ['Fecha', 'Fecha del documento'],
            ['N Documento', 'Numero de boleta o factura'],
            ['Monto', 'Monto en la moneda seleccionada'],
        ],
        [40, 140]
    )
    pdf.subsection_title('4b. Alojamiento')
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Detalle', 'Nombre del hotel o establecimiento'],
            ['Fecha', 'Fecha del documento'],
            ['N Documento', 'Numero de boleta o factura'],
            ['Monto', 'Monto en la moneda seleccionada'],
        ],
        [40, 140]
    )
    pdf.subsection_title('4c. Otros Gastos')
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Detalle', 'Descripcion del gasto'],
            ['Fecha', 'Fecha del documento'],
            ['N Documento', 'Numero de boleta o factura'],
            ['Monto', 'Monto en la moneda seleccionada'],
        ],
        [40, 140]
    )
    pdf.note_box('Los gastos vehiculares calculados automaticamente (traslado, peajes, acompanantes) aparecen en "Otros Gastos".')
    pdf.subsection_title('Escanear documentos con IA')
    pdf.body_text(
        'Haga clic en el boton "Escanear con IA" para enviar una imagen de su boleta o factura. '
        'La inteligencia artificial (Google Gemini) extraera automaticamente: Detalle, Fecha y Monto, '
        'y los colocara en una nueva fila de gastos.'
    )
    pdf.info_box('La funcion IA requiere conexion a internet. Si la cuota se agota, intente mas tarde.')

    # Seccion 5
    pdf.section_title('3.5 Seccion 5: Cuenta Contable y Jefatura')
    pdf.body_text(
        'Seleccione la cuenta contable que corresponde a este gasto y la jefatura que aprobara su rendicion.'
    )
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Cuenta Contable', 'Cuenta contable filtrada por su Centro de Costo (buscable)'],
            ['Jefatura Aprobadora', 'Su jefe directo que revisara la rendicion (buscable)'],
        ],
        [50, 130]
    )
    pdf.note_box('La Cuenta Contable se filtra automaticamente segun el Centro de Costo seleccionado.')

    # Envio
    pdf.section_title('3.6 Enviar y previsualizar')
    pdf.body_text('Antes de enviar, puede:')
    pdf.bullet('Hacer clic en "Revisar PDF" para ver una previsualizacion del documento final.')
    pdf.bullet('Hacer clic en "Enviar para Aprobacion" para someter la rendicion al flujo de aprobacion.')
    pdf.body_text(
        'Al enviar, el sistema: (1) calcula los costos vehiculares, (2) guarda la rendicion '
        'en la base de datos, (3) envia un email de notificacion a la Jefatura seleccionada, '
        'y (4) muestra un mensaje de confirmacion.'
    )


# ══════════════════════════════════════════════════════════════════════
# CAP 4: MIS RENDICIONES
# ══════════════════════════════════════════════════════════════════════

def cap_mis_rendiciones(pdf):
    pdf.add_page()
    pdf.chapter_title('Mis Rendiciones')
    pdf.body_text(
        'En la pestana "Mis Rendiciones" (parte inferior del formulario) puede ver el historial '
        'de todas sus rendiciones enviadas.'
    )
    pdf.section_title('4.1 Tabla de historial')
    pdf.simple_table(
        ['Columna', 'Descripcion'],
        [
            ['ID', 'Numero unico de la rendicion'],
            ['Monto', 'Total de gastos declarados'],
            ['Estado', 'Estado actual en el workflow'],
            ['Fecha', 'Fecha de registro en el sistema'],
            ['Accion', 'Botones para ver detalle o PDF'],
        ],
        [35, 145]
    )
    pdf.section_title('4.2 Estados de una rendicion')
    pdf.simple_table(
        ['Estado', 'Significado', 'Color'],
        [
            ['pendiente', 'Esperando aprobacion de Jefatura', 'Gris'],
            ['APROBADO_POR_JEFATURA', 'Aprobada por Jefatura, esperando Encargado', 'Naranja'],
            ['PROCESADO_ENCARGADO', 'Procesada finalmente por Encargado', 'Verde'],
            ['RECHAZADO_POR_JEFATURA', 'Rechazada por Jefatura', 'Rojo'],
            ['RECHAZADO_POR_ENCARGADO', 'Rechazada por Encargado', 'Rojo'],
        ],
        [55, 85, 30]
    )
    pdf.section_title('4.3 Ver PDF')
    pdf.body_text(
        'Haga clic en el icono de ojo para ver el PDF de su rendicion. Si la rendicion '
        'ya fue aprobada, vera el PDF con sello de aprobacion. Si esta pendiente, vera '
        'una version preliminary sin sello.'
    )
    pdf.section_title('4.4 Editar rendicion')
    pdf.body_text(
        'Si su rendicion tiene estado "pendiente" (rechazada), puede editarla haciendo clic '
        'en el icono de lapiz. Esto cargara todos los datos en el formulario para su modificacion. '
        'Una vez editada, puede enviarla nuevamente.'
    )


# ══════════════════════════════════════════════════════════════════════
# CAP 5: APROBACION (JEFATURA)
# ══════════════════════════════════════════════════════════════════════

def cap_aprobaciones(pdf):
    pdf.add_page()
    pdf.chapter_title('Aprobacion de Rendiciones (Jefatura)')
    pdf.body_text(
        'Si tiene el rol de Jefatura, vera en el menu lateral "Aprobaciones". '
        'Esta seccion muestra las rendiciones asignadas a su email que estan pendientes de revision.'
    )
    pdf.section_title('5.1 Panel de aprobaciones')
    pdf.body_text(
        'Al entrar, ve una tabla con las rendiciones pendientes. Cada fila muestra: '
        'ID, Funcionario, RUT, Monto, Moneda y Fecha.'
    )
    pdf.section_title('5.2 Ver detalle de una rendicion')
    pdf.body_text(
        'Haga clic en el icono de ojo para ver el detalle completo. Podra ver todas las '
        'tablas de gastos (Comision, Alojamiento, Alimentacion, Otros) y una vista previa '
        'del PDF integrada en la pagina.'
    )
    pdf.section_title('5.3 Aprobar una rendicion')
    pdf.step(1, 'Revise cuidadosamente todos los gastos y documentos de respaldo.')
    pdf.step(2, 'Ingrese su RUT en el campo "Confirmar RUT" como mecanismo de identificacion.')
    pdf.step(3, 'Haga clic en "Aprobar Rendicion".')
    pdf.body_text(
        'Al aprobar: (1) se genera el PDF final con sello de aprobacion digital (incluye su nombre, '
        'RUT, fecha y codigo QR), (2) el estado cambia a "APROBADO_POR_JEFATURA", '
        '(3) la rendicion pasa al panel del Encargado para procesamiento final.'
    )
    pdf.note_box('La confirmacion de RUT es obligatoria. Esto genera un sello de firma digital vinculado a su cedula de identidad.')
    pdf.section_title('5.4 Rechazar una rendicion')
    pdf.step(1, 'Ingrese el motivo del rechazo en el campo "Motivo del rechazo".')
    pdf.step(2, 'Haga clic en "Rechazar Rendicion".')
    pdf.body_text(
        'Al rechazar: (1) el estado cambia a "RECHAZADO_POR_JEFATURA", '
        '(2) se envia un email al funcionario con el motivo del rechazo.'
    )


# ══════════════════════════════════════════════════════════════════════
# CAP 6: PANEL ENCARGADO
# ══════════════════════════════════════════════════════════════════════

def cap_encargado(pdf):
    pdf.add_page()
    pdf.chapter_title('Panel Encargado')
    pdf.body_text(
        'El panel del Encargado es el centro de control para el procesamiento final de rendiciones. '
        'Acceda desde el menu lateral seleccionando "Encargado".'
    )
    pdf.section_title('6.1 KPIs (tarjetas resumen)')
    pdf.simple_table(
        ['KPI', 'Descripcion'],
        [
            ['TODAS', 'Total de rendiciones en el sistema'],
            ['POR PROCESAR', 'Rendiciones aprobadas por Jefatura, listas para procesar'],
            ['PROCESADAS', 'Rendiciones ya procesadas por el Encargado'],
            ['EN JEFATURA', 'Rendiciones pendientes de aprobacion por Jefatura'],
        ],
        [50, 130]
    )
    pdf.section_title('6.2 Filtros')
    pdf.body_text('Use las tarjetas KPI o el selector de filtros para ver:')
    pdf.bullet('Todas: muestra todas las rendiciones sin filtro de estado.')
    pdf.bullet('Por Procesar: solo rendiciones con estado APROBADO_POR_JEFATURA (excluye las suyas propias).')
    pdf.bullet('En Jefatura: rendiciones pendientes asignadas a su email.')
    pdf.bullet('Procesadas: rendiciones que usted ya proceso.')
    pdf.section_title('6.3 Tomar una rendicion')
    pdf.body_text(
        'En la lista "Por Procesar", si ve una rendicion creada por otro encargado, puede '
        'hacer clic en el icono de mano para "tomarla". Esto asigna la rendicion a usted '
        'y evita que otro encargado la procese simultaneamente.'
    )
    pdf.info_box('Las rendiciones creadas por usted mismo aparecen con un badge "Mi rendicion" pero no puede tomarlas. Otro encargado debe procesarlas.')
    pdf.section_title('6.4 Ver detalle')
    pdf.body_text(
        'Haga clic en el icono de ojo para ver el detalle completo de la rendicion. '
        'Podra ver todas las tablas de gastos, la vista previa del PDF, y las acciones disponibles.'
    )
    pdf.section_title('6.5 Editar cuentas contables')
    pdf.body_text(
        'En la vista de detalle, la tabla de Comision de Servicios tiene una columna "Cuenta Contable" '
        'con un selector desplegable. Puede cambiar la cuenta contable de cada fila segun corresponda. '
        'Haga clic en "Guardar Cuentas Contables" para persistir los cambios.'
    )
    pdf.note_box('Los cambios en cuentas contables se guardan en la base de datos y se comparan con los originales al procesar. Si hubo cambios, se enviara un email de notificacion al funcionario.')
    pdf.section_title('6.6 Procesar una rendicion')
    pdf.step(1, 'Revise todos los gastos y verifique las cuentas contables asignadas.')
    pdf.step(2, 'Haga clic en "Aprobar y Procesar Final".')
    pdf.body_text(
        'Al procesar: (1) se genera el PDF final, (2) se envia un email al funcionario '
        'con el PDF adjunto, (3) si hubo correcciones a cuentas contables, se envia un '
        'segundo email con una tabla detallando los cambios (valor anterior vs nuevo valor), '
        '(4) el estado cambia a "PROCESADO_ENCARGADO".'
    )
    pdf.section_title('6.7 Rechazar una rendicion')
    pdf.body_text(
        'Ingrese un comentario y haga clic en "Rechazar". Se notificara al funcionario '
        'por email con el motivo del rechazo.'
    )
    pdf.section_title('6.8 Reasignar jefatura')
    pdf.body_text(
        'Si la rendicion debe ser revisada por otro jefe, seleccione la nueva jefatura '
        'en el selector y haga clic en "Reasignar y Reiniciar". La rendicion volvera '
        'al estado "pendiente" con la nueva jefatura asignada.'
    )


# ══════════════════════════════════════════════════════════════════════
# CAP 7: RESUMEN EJECUTIVO
# ══════════════════════════════════════════════════════════════════════

def cap_resumen_ejecutivo(pdf):
    pdf.add_page()
    pdf.chapter_title('Resumen Ejecutivo')
    pdf.body_text(
        'El Resumen Ejecutivo es un dashboard analitico que muestra gastos agregados '
        'por Centro de Costo y Cuenta Contable. Acceda desde el boton "Resumen Ejecutivo" '
        'en el panel del Encargado.'
    )
    pdf.section_title('7.1 Filtros disponibles')
    pdf.simple_table(
        ['Filtro', 'Tipo', 'Descripcion'],
        [
            ['Desde', 'Fecha', 'Fecha de inicio del rango'],
            ['Hasta', 'Fecha', 'Fecha de fin del rango'],
            ['Usuario', 'Buscable', 'Filtrar por funcionario especifico'],
            ['Sucursal', 'Buscable', 'Filtrar por terminal/sucursal'],
            ['Centro de Costo', 'Buscable', 'Filtrar por codigo de centro de costo'],
            ['Cuenta Contable', 'Buscable', 'Filtrar por cuenta contable'],
        ],
        [45, 30, 100]
    )
    pdf.section_title('7.2 Tabla de resultados')
    pdf.body_text(
        'La tabla muestra los gastos agrupados por: Codigo CC, Centro de Costo, '
        'Cuenta Contable y Concepto. Para cada grupo se muestra el numero de '
        'Transacciones y el Monto Total.'
    )
    pdf.body_text(
        'Los subtotales por Centro de Costo aparecen resaltados, y al final '
        'se muestra el Total General.'
    )
    pdf.section_title('7.3 Exportar datos')
    pdf.bullet('Excel: Haga clic en "Exportar Excel" para descargar un archivo .xlsx con los datos filtrados.')
    pdf.bullet('PDF: Use el boton de exportar PDF de la tabla.')
    pdf.bullet('Imprimir: Use el boton de imprimir para una copia fisica.')


# ══════════════════════════════════════════════════════════════════════
# CAP 8: GESTION DE USUARIOS
# ══════════════════════════════════════════════════════════════════════

def cap_usuarios(pdf):
    pdf.add_page()
    pdf.chapter_title('Gestion de Usuarios')
    pdf.body_text(
        'Solo los administradores (rol Admin) pueden gestionar usuarios. '
        'Acceda desde el menu lateral seleccionando "Usuarios".'
    )
    pdf.section_title('8.1 Lista de usuarios')
    pdf.body_text(
        'Se muestra una tabla con todos los usuarios registrados. Puede buscar '
        'por nombre, email, RUT, empresa o cargo usando el campo de busqueda.'
    )
    pdf.simple_table(
        ['Columna', 'Descripcion'],
        [
            ['ID', 'Identificador unico'],
            ['Nombre', 'Nombre completo del usuario'],
            ['Email', 'Email corporativo (usado como login)'],
            ['RUT', 'Numero de RUT'],
            ['Empresa', 'Empresa a la que pertenece'],
            ['Cargo', 'Cargo o funcion'],
            ['Roles', 'Roles asignados (separados por coma)'],
            ['Terminal', 'Terminal o sucursal asignada'],
        ],
        [30, 150]
    )
    pdf.section_title('8.2 Crear usuario')
    pdf.body_text('Haga clic en "Crear Usuario" para abrir el formulario.')
    pdf.simple_table(
        ['Campo', 'Obligatorio', 'Descripcion'],
        [
            ['Nombre Completo', 'Si', 'Nombre y apellido del usuario'],
            ['Email', 'Si', 'Email corporativo (sirve como nombre de usuario)'],
            ['RUT', 'No', 'Numero de RUT (formato: 12345678-9 o 12345678-K)'],
            ['Contrasena', 'Si', 'Contrasena inicial del usuario'],
            ['Centros de Costo', 'No', 'Centros de costo asignados (multi-seleccion)'],
            ['Jefatura Aprueba', 'No', 'Email del jefe directo'],
            ['Terminal Asignado', 'No', 'Terminal o sucursal'],
            ['Empresa', 'No', 'Nombre de la empresa'],
            ['Cargo', 'No', 'Cargo o funcion'],
            ['Roles', 'Si', 'Usuario, Jefatura, Encargado, Admin'],
        ],
        [40, 22, 115]
    )
    pdf.subsection_title('Asignacion de Cuentas Contables por CC')
    pdf.body_text(
        'Para cada Centro de Costo asignado al usuario, aparece un selector de cuentas contables. '
        'Seleccione las cuentas que el usuario podra utilizar al crear rendiciones en ese centro de costo.'
    )
    pdf.note_box('La contrasena se almacena en formato hash (werkzeug). No es posible recuperarla, solo restablecerla.')
    pdf.section_title('8.3 Editar usuario')
    pdf.body_text(
        'Haga clic en el icono de lapiz en la columna de Acciones. Se abrira un modal '
        'con todos los campos pre-cargados. Modifique lo que necesite y haga clic en "Guardar".'
    )
    pdf.section_title('8.4 Cambiar contrasena')
    pdf.body_text(
        'Desde el modal de edicion, ingrese la nueva contrasena en el campo correspondiente '
        'y haga clic en "Guardar".'
    )
    pdf.section_title('8.5 Eliminar usuario')
    pdf.body_text(
        'Haga clic en el icono de papelera. Se pedira confirmacion antes de eliminar. '
        'No es posible eliminar su propio usuario ni el usuario Super.'
    )
    pdf.info_box('El usuario Super (Super Admin) no puede ser editado, eliminado ni tener su contrasena cambiada desde la interfaz.')


# ══════════════════════════════════════════════════════════════════════
# CAP 9: MANTENCION DE DATOS
# ══════════════════════════════════════════════════════════════════════

def cap_mantencion(pdf):
    pdf.add_page()
    pdf.chapter_title('Mantencion de Datos')
    pdf.body_text(
        'Solo los administradores pueden acceder a la mantencion de datos de referencia. '
        'Acceda desde el menu lateral seleccionando "Mantencion".'
    )
    pdf.section_title('9.1 Tabla de trayectos y costos')
    pdf.body_text('Configura las rutas de viaje y sus costos asociados:')
    pdf.simple_table(
        ['Campo', 'Descripcion', 'Uso'],
        [
            ['Origen', 'Ciudad de origen', 'Seleccion en formulario'],
            ['Destino', 'Ciudad de destino', 'Seleccion en formulario'],
            ['KM Base', 'Distancia en kilometros (ida)', 'Calculo de costo vehicular'],
            ['Mult. Peaje', 'Multiplicador de peajes', 'Calculo de peajes'],
            ['Peaje ($)', 'Costo base del peaje', 'Calculo de peajes'],
            ['Factor', 'Factor de ajuste del costo', 'Calculo vehicular (km x 2 x factor)'],
            ['Desayuno', 'Monto diario para desayuno', 'Tope USD'],
            ['Almuerzo', 'Monto diario para almuerzo', 'Tope USD'],
            ['Cena', 'Monto diario para cena', 'Tope USD'],
        ],
        [30, 70, 80]
    )
    pdf.section_title('9.2 Jefaturas')
    pdf.body_text(
        'Administra la lista de jefes directos que pueden aprobar rendiciones. '
        'Los cambios aqui se sincronizan automaticamente con el rol "jefatura" en la tabla de usuarios.'
    )
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Nombre', 'Nombre completo del jefe'],
            ['Email', 'Email corporativo (debe coincidir con el usuario)'],
        ],
        [50, 130]
    )
    pdf.section_title('9.3 Terminales')
    pdf.body_text('Administra las terminales o sucursales de la empresa:')
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Nombre', 'Nombre de la terminal (ej: "Placilla")'],
            ['Codigo Interno', 'Codigo corto para referencia'],
            ['Activo', 'Si/No - si la terminal esta activa'],
        ],
        [50, 130]
    )
    pdf.section_title('9.4 Cuentas Contables')
    pdf.body_text('Administra las cuentas contables disponibles para clasificar gastos:')
    pdf.simple_table(
        ['Campo', 'Descripcion'],
        [
            ['Codigo Cuenta', 'Codigo unico de la cuenta (ej: 750521)'],
            ['Detalle 1', 'Descripcion detallada de la cuenta'],
            ['Concepto Amigable', 'Nombre corto amigable para el usuario'],
        ],
        [50, 130]
    )
    pdf.section_title('9.5 Centros de Costo')
    pdf.body_text('Administra los centros de costo y asigna cuentas contables a cada uno:')
    pdf.bullet('Codigo CC: Codigo unico del centro de costo.')
    pdf.bullet('Detalle CC: Descripcion del centro de costo.')
    pdf.bullet('Asignacion CC-Cuentas: Seleccione un CC y asigne las cuentas contables disponibles para ese centro.')
    pdf.section_title('9.6 Topes USD')
    pdf.body_text(
        'Configura los montos maximos en dolares para gastos de alimentacion en viajes '
        'internacionales. Se aplica por tipo de comida: Desayuno, Almuerzo y Cena.'
    )
    pdf.info_box('Los topes USD se usan como referencia. El sistema no bloquea el envio si se exceden, pero los muestra en el PDF.')


# ══════════════════════════════════════════════════════════════════════
# CAP 10: REFERENCIA TECNICA
# ══════════════════════════════════════════════════════════════════════

def cap_referencia_tecnica(pdf):
    pdf.add_page()
    pdf.chapter_title('Referencia Tecnica')

    pdf.section_title('10.1 Estados del workflow')
    pdf.body_text('Diagrama de estados de una rendicion:')
    pdf.simple_table(
        ['Estado', 'Transicion', 'Quien ejecuta'],
        [
            ['pendiente', 'Estado inicial al enviar', 'Usuario'],
            ['APROBADO_POR_JEFATURA', 'Jefatura aprueba la rendicion', 'Jefatura'],
            ['RECHAZADO_POR_JEFATURA', 'Jefatura rechaza la rendicion', 'Jefatura'],
            ['PROCESADO_ENCARGADO', 'Encargado procesa finalmente', 'Encargado'],
            ['RECHAZADO_POR_ENCARGADO', 'Encargado rechaza la rendicion', 'Encargado'],
        ],
        [55, 70, 50]
    )
    pdf.body_text('Transiciones validas:')
    pdf.bullet('pendiente -> APROBADO_POR_JEFATURA (aprobacion normal)')
    pdf.bullet('pendiente -> RECHAZADO_POR_JEFATURA (rechazo por jefatura)')
    pdf.bullet('APROBADO_POR_JEFATURA -> PROCESADO_ENCARGADO (procesamiento final)')
    pdf.bullet('APROBADO_POR_JEFATURA -> RECHAZADO_POR_ENCARGADO (rechazo por encargado)')
    pdf.bullet('APROBADO_POR_JEFATURA -> pendiente (reasignacion de jefatura)')

    pdf.section_title('10.2 Calculo de costos vehiculares')
    pdf.body_text('Cuando el tipo de traslado es "Vehiculo propio", se calculan automaticamente:')
    pdf.subsection_title('Costo base del traslado')
    pdf.body_text('Costo Base = KM Base x 2 x Factor')
    pdf.body_text('Donde:')
    pdf.bullet('KM Base: distancia en kilometros de la tabla trayectos (solo ida).')
    pdf.bullet('2: factor de viaje redondo (ida y vuelta).')
    pdf.bullet('Factor: coeficiente de ajuste configurado en la tabla trayectos.')
    pdf.subsection_title('Costo de peajes')
    pdf.body_text('Peajes = Monto Peaje Base x Multiplicador Peaje')
    pdf.subsection_title('Costo de acompanantes')
    pdf.body_text('Acompanantes = Costo Base x 0.2 x Numero de Acompanantes')
    pdf.body_text('El 20% es un porcentaje fijo del costo base por cada acompanante.')
    pdf.note_box('Los costos vehiculares se agregan como filas adicionales en la tabla "Otros Gastos" del PDF.')

    pdf.section_title('10.3 Funcionalidad de IA (OCR)')
    pdf.body_text('El sistema integra Google Gemini para dos funciones:')
    pdf.subsection_title('Escanear boletas/facturas')
    pdf.bullet('Endpoint: POST /rendiciones/ai-scan')
    pdf.bullet('Envia la primera imagen adjunta a Gemini con un prompt de extraccion.')
    pdf.bullet('Devuelve: Detalle, Razon Social, Fecha de Emision, Monto Total.')
    pdf.bullet('Modelos en orden: gemini-2.5-flash, gemini-2.0-flash, gemini-flash-latest.')
    pdf.bullet('Manejo de cuota agotada: reintenta una vez despues de 10 segundos.')
    pdf.subsection_title('Escanear cedula de identidad')
    pdf.bullet('Endpoint: POST /usuarios/ocr-id')
    pdf.bullet('Envia imagen de cedula a Gemini para extraer nombre y RUT.')
    pdf.bullet('Autocompleta los campos del formulario de crear usuario.')

    pdf.section_title('10.4 Generacion de PDF')
    pdf.body_text('El PDF se genera con la libreria fpdf2 y tiene esta estructura:')
    pdf.bullet('Encabezado: Logo HGT, titulo "RENDICION DE GASTOS", moneda.')
    pdf.bullet('Seccion Funcionario: Nombre, RUT, Centro de Costo, Email, Jefatura.')
    pdf.bullet('Comision de Servicios: Tabla con detalles del viaje.')
    pdf.bullet('Anticipo: Fecha y monto del anticipo.')
    pdf.bullet('Alojamiento/Alimentacion/Otros: Tablas de gastos con subtotales.')
    pdf.bullet('Totales: Total Desembolsos, Diferencia a favor de HGT/Funcionario.')
    pdf.bullet('Firmas: Espacios para firma del funcionario y jefe directo.')
    pdf.bullet('Sello de aprobacion: Texto con RUT, fecha y codigo QR (si esta aprobado).')
    pdf.bullet('Comprobantes: Pagas adicionales con imagenes de boletas (hasta 4 por pagina).')

    pdf.section_title('10.5 Notificaciones por email')
    pdf.simple_table(
        ['Evento', 'Destinatario', 'Asunto'],
        [
            ['Nueva rendicion', 'Jefatura', 'Nueva Rendicion de Gastos pendiente'],
            ['Rechazo por Jefatura', 'Funcionario', 'Rendicion de Gastos RECHAZADA'],
            ['Procesamiento final', 'Funcionario', 'Rendicion de Gastos APROBADA'],
            ['Correcciones', 'Funcionario', 'Rendicion de Gastos - Correcciones'],
            ['Rechazo por Encargado', 'Funcionario', 'Rendicion de Gastos RECHAZADA'],
        ],
        [45, 40, 100]
    )
    pdf.note_box('Si la direccion de email es invalida o el servidor SMTP no esta configurado, el sistema registra el error pero no bloquea la operacion.')

    pdf.section_title('10.6 Seguridad')
    pdf.bullet('Contrasenas: Almacenadas con werkzeug.security (hash + salt).')
    pdf.bullet('CSRF: Token en todas las peticiones POST (TTL: 1 hora).')
    pdf.bullet('Sesiones: Almacenamiento en disco con lifetime configurable (default: 3600s).')
    pdf.bullet('Headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Cache-Control: no-store.')
    pdf.bullet('Login: Delay de 1 segundo en credenciales incorrectas (anti brute-force).')
    pdf.bullet('Permisos: Decorador @permission_required verifica rol + super_user bypass.')
    pdf.bullet('AJAX: Peticiones con header X-Requested-With para distinguir de navegacion normal.')

    pdf.section_title('10.7 Endpoints principales')
    pdf.simple_table(
        ['Ruta', 'Metodo', 'Descripcion'],
        [
            ['/login', 'GET/POST', 'Inicio de sesion'],
            ['/rendiciones', 'GET', 'Formulario y historial'],
            ['/rendiciones/submit', 'POST', 'Enviar rendicion'],
            ['/rendiciones/preview', 'POST', 'Previsualizar PDF'],
            ['/rendiciones/ai-scan', 'POST', 'Escanear documento con IA'],
            ['/aprobaciones', 'GET', 'Panel de aprobaciones'],
            ['/aprobaciones/<rid>/approve', 'POST', 'Aprobar rendicion'],
            ['/aprobaciones/<rid>/reject', 'POST', 'Rechazar rendicion'],
            ['/encargado', 'GET', 'Panel del encargado'],
            ['/encargado/<rid>/procesar', 'POST', 'Procesar rendicion'],
            ['/encargado/<rid>/tomar', 'POST', 'Tomar rendicion'],
            ['/encargado/dashboard-data', 'GET', 'Resumen Ejecutivo'],
            ['/usuarios', 'GET', 'Gestion de usuarios'],
            ['/mantencion', 'GET', 'Panel de mantencion'],
        ],
        [60, 30, 95]
    )


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    pdf = ManualPDF()
    pdf.set_title('Manual de Usuario - HGT Rendiciones de Gastos')
    pdf.set_author('HGT Chile Logistics')

    # Generar contenido
    portada(pdf)
    indice(pdf)
    cap_introduccion(pdf)
    cap_acceso(pdf)
    cap_crear_rendicion(pdf)
    cap_mis_rendiciones(pdf)
    cap_aprobaciones(pdf)
    cap_encargado(pdf)
    cap_resumen_ejecutivo(pdf)
    cap_usuarios(pdf)
    cap_mantencion(pdf)
    cap_referencia_tecnica(pdf)

    # Guardar
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Manual_Usuario_HGT_Rendiciones.pdf')
    pdf.output(output_path)
    print(f'Manual generado: {output_path}')
    print(f'Total de paginas: {pdf.page_no()}')


if __name__ == '__main__':
    main()
