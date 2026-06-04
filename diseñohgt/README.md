# HGT Design System - Diseñohgt

Este directorio contiene el sistema de diseño visual corporativo de HGT, diseñado para ser reutilizado por otros sistemas.

## Estructura
- `/css/hgt_style.css`: Estilos globales, variables de color, tipografía y componentes.
- `/js/hgt_core.js`: Controladores para modales, alertas premium, datatables y sidebar.
- `/components/`: Ejemplos HTML de cada componente.
- `/assets/`: Imágenes y logos corporativos.
- `tokens.json`: Variables de color y diseño en formato JSON.

## Cómo usar

1. **Importar CSS y Fuentes**:
   ```html
   <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
   <link rel="stylesheet" href="path/to/diseñohgt/css/hgt_style.css">
   <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
   ```

2. **Importar JavaScript**:
   ```html
   <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
   <script src="path/to/diseñohgt/js/hgt_core.js"></script>
   ```

3. **Colores Principales**:
   - `var(--hgt-orange)`: #ff6600 (Color Primario)
   - `var(--hgt-greyblue)`: #1a222d (Fondo Sidebar/Login)
   - `var(--hgt-aqua)`: #4ecdc4 (Accentos)

## Componentes Disponibles
- **Botones**: Usar clase `.btn` con `.btn-primary`, `.btn-secondary`, o `.btn-danger`.
- **Tablas**: Usar clase `.table` dentro de un `.table-container`.
- **Modals**: Usar `openModal(id)` y `closeModal(id)`.
- **Alertas Premium**: Usar `showPremiumAlert(category, message)`.
- **Confirmaciones**: Usar `showPremiumConfirm(message, form)`.

## Notas
El sistema está optimizado para trabajar con **DataTables** y **FontAwesome 6**.
