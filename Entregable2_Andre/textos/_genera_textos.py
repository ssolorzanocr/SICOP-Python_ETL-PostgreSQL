"""Genera las secciones de texto (docx) del segundo entregable a partir de los
resultados del cuaderno. Formato del reglamento del TFM: Times New Roman 12,
títulos 14, interlineado 1,5, márgenes 3 cm / 2,5 cm, APA 7."""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

FIG = Path(__file__).parent.parent / "figuras"


def documento():
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(3)
        s.top_margin = s.bottom_margin = Cm(2.5)
    base = doc.styles["Normal"]
    base.font.name, base.font.size = "Times New Roman", Pt(12)
    base.paragraph_format.line_spacing = 1.5
    base.paragraph_format.space_after = Pt(6)
    for nombre, tam in (("Heading 1", 14), ("Heading 2", 13), ("Heading 3", 12)):
        st = doc.styles[nombre]
        st.font.name, st.font.size, st.font.bold = "Times New Roman", Pt(tam), True
    return doc


def h(doc, texto, level):
    """Título con Times New Roman negro (el tema de Word impone Calibri azul)."""
    from docx.oxml.ns import qn
    from docx.shared import RGBColor
    t = doc.add_heading(texto, level=level)
    for r in t.runs:
        r.font.name = "Times New Roman"
        r.font.color.rgb = RGBColor(0, 0, 0)
        r._element.rPr.rFonts.set(qn("w:asciiTheme"), "")
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            r._element.rPr.rFonts.attrib.pop(qn(attr), None)
    return t


def p(doc, texto, cursiva=False, sangria=False):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = par.add_run(texto)
    run.italic = cursiva
    if sangria:
        par.paragraph_format.left_indent = Cm(1.27)
        par.paragraph_format.first_line_indent = Cm(-1.27)
    return par


def tabla(doc, numero, titulo, cabecera, filas, nota):
    doc.add_paragraph().add_run(f"Tabla {numero}").bold = True
    doc.add_paragraph().add_run(titulo).italic = True
    t = doc.add_table(rows=1, cols=len(cabecera))
    t.style = "Table Grid"
    for c, h in zip(t.rows[0].cells, cabecera):
        c.text = h
        c.paragraphs[0].runs[0].bold = True
    for fila in filas:
        for c, v in zip(t.add_row().cells, fila):
            c.text = str(v)
    for fila in t.rows:
        for c in fila.cells:
            for par in c.paragraphs:
                par.paragraph_format.line_spacing = 1.0
                for r in par.runs:
                    r.font.size = Pt(10)
    n = doc.add_paragraph()
    n.add_run("Nota. ").italic = True
    n.add_run(nota).font.size = Pt(10)


def figura(doc, numero, titulo, archivo, nota, ancho=15):
    doc.add_paragraph().add_run(f"Figura {numero}").bold = True
    doc.add_paragraph().add_run(titulo).italic = True
    doc.add_picture(str(FIG / archivo), width=Cm(ancho))
    n = doc.add_paragraph()
    n.add_run("Nota. ").italic = True
    n.add_run(nota).font.size = Pt(10)


def referencias(doc, refs):
    h(doc, "Referencias de esta sección", level=2)
    p(doc, "(Para integrar en la bibliografía general del documento, en orden alfabético.)", cursiva=True)
    for r in refs:
        p(doc, r, sangria=True)


# =====================================================================
# 1. Memoria de la Asignatura 7 — preprocesamiento y análisis no supervisado
# =====================================================================
doc = documento()
h(doc, "Análisis no supervisado: segmentación de proveedores", level=1)
p(doc, "Componente de la memoria de la Asignatura 7 (Modelado predictivo con Machine Learning). "
       "Redacción: André Plannerer. Código reproducible: cuaderno clustering_proveedores.ipynb "
       "(Anexo). Esta sección cubre el apartado 4.4 del enunciado y aporta al 4.1 "
       "(preprocesamiento).", cursiva=True)

h(doc, "Objetivo y relación con el TFM", level=2)
p(doc, "El modelo supervisado del grupo estima la probabilidad de que una oferta resulte "
       "adjudicada (caso de uso 3). Para que esa estimación sea útil, el proveedor necesita "
       "además un marco de referencia: saber con qué tipo de competidores se enfrenta y a qué "
       "perfil de proveedor se parece. Ese es el caso de uso 2 del primer avance, "
       "«Caracterización de proveedores», cuya herramienta central es el benchmarking. El "
       "análisis no supervisado busca construir ese marco agrupando a los proveedores que "
       "ofertan en SICOP según su comportamiento observado, sin imponer categorías previas.")
p(doc, "El análisis también se vincula con la hipótesis 3 del primer avance («existen áreas de "
       "oportunidad desatendidas»), que se aborda desde dos niveles: el de proveedor (¿existe un "
       "grupo que compite en espacios con poca competencia?) y el de mercado (¿qué segmentos de "
       "producto combinan mucha demanda con poca competencia?).")

h(doc, "Datos y unidad de análisis", level=2)
p(doc, "Se utilizó la base sicop.duckdb generada por el pipeline automatizado del grupo "
       "(esquema final, datos de enero de 2025 a septiembre de 2026). La unidad de análisis es "
       "el proveedor: las ofertas línea a línea se agregaron en una fila por proveedor mediante "
       "una consulta SQL documentada en el anexo. De los 4.379 proveedores con al menos una "
       "oferta, se segmentaron los 1.990 que tienen cinco o más líneas ofertadas ya resueltas; "
       "con menos observaciones la tasa de éxito es ruido estadístico. Estos 1.990 proveedores "
       "concentran el 96,1 % de las líneas ofertadas. Los 2.389 restantes se describen como "
       "proveedores ocasionales.")
p(doc, "Se tomaron tres decisiones para evitar sesgos. Primero, los montos y precios se "
       "convirtieron a colones solo cuando la línea está en colones o en dólares, porque se "
       "verificó que la columna tipo_cambio_crc contiene el tipo de cambio del dólar en todas "
       "las filas, incluso en las líneas en euros. Segundo, la tasa de éxito se calculó solo "
       "sobre líneas resueltas, para no contar como perdida una oferta que sigue en evaluación "
       "(censura de la variable). Tercero, el precio se expresó en términos relativos (precio "
       "ofertado sobre la mediana de las ofertas de la misma línea), porque los precios "
       "absolutos de productos distintos no son comparables.")

h(doc, "Preprocesamiento", level=2)
tabla(doc, 1, "Variables del análisis de segmentación y su transformación",
      ["Variable", "Definición", "Transformación", "Justificación"],
      [["Volumen", "Líneas ofertadas", "log(1 + x)", "Asimetría 17,1 → 0,9"],
       ["Segmentos", "Segmentos UNSPSC distintos", "log(x)", "Asimetría 3,2 → 0,5"],
       ["Instituciones", "Instituciones distintas", "log(x); nulos → 1", "Asimetría 7,5 → 0,5"],
       ["Tasa de éxito", "Ganadas / resueltas", "Ninguna", "Acotada en [0, 1]"],
       ["Competidores", "Competidores promedio por línea", "log(1 + x)", "Reduce la cola derecha"],
       ["Precio relativo", "Mediana de precio / mediana de la línea", "Recorte [0,25; 4] y log",
        "Extremos por errores de unidad; simetría"],
       ["Ticket medio", "Monto adjudicado / línea ganada (₡)", "log(1 + x)", "Asimetría 14,7 → −1,1"]],
      "Asimetría medida con el coeficiente de Fisher antes y después de transformar. "
      "Elaboración propia.")
p(doc, "Después de las transformaciones, todas las variables se estandarizaron (media 0, desvío "
       "1) con StandardScaler. El algoritmo elegido usa distancia euclídea: sin escalar, el "
       "ticket medio (millones de colones) dominaría a la tasa de éxito (entre 0 y 1). Se "
       "prefirió StandardScaler a MinMaxScaler porque este último es sensible a los valores "
       "extremos que persisten tras la transformación logarítmica. A los 140 proveedores sin "
       "ninguna línea con competencia, donde el precio relativo no está definido, se les imputó "
       "el valor neutro 1. Las correlaciones entre variables no superan 0,67 en valor absoluto, "
       "por lo que se mantuvieron todas.")
figura(doc, 1, "Distribución de las variables antes y después de la transformación logarítmica",
       "fig1_transformaciones.png", "Elaboración propia con datos del Observatorio de Compra Pública.")

h(doc, "Elección del método y del número de grupos", level=2)
p(doc, "Se eligió KMeans (MacQueen, 1967) por tres razones. Las variables son continuas y quedan "
       "escaladas. El objetivo es obtener pocos perfiles interpretables, cuyos centroides "
       "representan al «proveedor típico» de cada grupo y pueden mostrarse en la aplicación. Y "
       "un proveedor nuevo se asigna al centroide más cercano sin reentrenar, lo que permite "
       "usar el modelo en producción. Se descartó DBSCAN porque no produce perfiles comparables "
       "y trata como ruido a los proveedores atípicos, que son precisamente los de mayor volumen. "
       "Se descartó el clustering jerárquico por su costo en memoria, sin ventaja interpretativa "
       "para este caso. Se utilizó la implementación de scikit-learn (Pedregosa et al., 2011).")
p(doc, "Se evaluaron soluciones con k entre 2 y 8 según cuatro criterios: la inercia (método del "
       "codo); el coeficiente de silueta (Rousseeuw, 1987), mejor cuanto más alto; el índice de "
       "Davies-Bouldin (Davies y Bouldin, 1979), mejor cuanto más bajo; y la estabilidad, medida "
       "con el índice de Rand ajustado (Hubert y Arabie, 1985) entre la solución de referencia "
       "y tres inicializaciones distintas.")
tabla(doc, 2, "Criterios de validación interna según el número de grupos",
      ["k", "Silueta", "Davies-Bouldin", "Estabilidad (ARI)", "Grupo más pequeño"],
      [["2", "0,203", "1,617", "0,997", "692"], ["3", "0,274", "1,344", "0,998", "413"],
       ["4", "0,260", "1,369", "0,995", "385"], ["5", "0,268", "1,252", "1,000", "49"],
       ["6", "0,253", "1,362", "0,995", "48"], ["7", "0,261", "1,279", "0,993", "27"],
       ["8", "0,237", "1,342", "0,985", "27"]],
      "KMeans con 20 inicializaciones por solución. Elaboración propia.")
p(doc, "Se eligió k = 4. La silueta máxima corresponde a k = 3 (0,274), pero la diferencia con "
       "k = 4 (0,260) es pequeña, y ambos valores indican una estructura de fuerza moderada, "
       "esperable en datos de comportamiento que forman un continuo. k = 4 se prefiere por su "
       "utilidad para el caso de uso: separa a los proveedores de nicho, que ganan casi todo lo "
       "que ofertan con menos de un competidor por línea, de los ganadores de alto volumen, con "
       "los que k = 3 los mezcla. La solución es estable (ARI 0,995) y su grupo más pequeño "
       "tiene 385 proveedores. A partir de k = 5 aparecen grupos de menos de 50 proveedores, "
       "formados por atípicos de precio y sin una lectura de negocio nueva.")
figura(doc, 2, "Inercia y coeficiente de silueta según el número de grupos",
       "fig2_seleccion_k.png", "Línea discontinua: k elegido. Elaboración propia.")

h(doc, "Resultados: cuatro perfiles de proveedor", level=2)
tabla(doc, 3, "Perfil de los grupos (medianas)",
      ["Grupo", "Proveedores", "Líneas ofertadas", "Segmentos", "Tasa de éxito",
       "Competidores por línea", "% del monto adjudicado"],
      [["Generalistas de alto volumen", "450", "104", "7", "33 %", "3,1", "40,6 %"],
       ["Competidores focalizados", "653", "16", "2", "28 %", "3,6", "33,8 %"],
       ["Nicho con poca competencia", "502", "11", "2", "100 %", "0,7", "25,2 %"],
       ["Sin adjudicaciones", "385", "10", "2", "0 %", "4,0", "0,4 %"]],
      "Montos convertidos a colones. Elaboración propia.")
figura(doc, 3, "Perfil estandarizado de cada grupo", "fig3_perfil_grupos.png",
       "Cada celda es la media de la variable estandarizada; 0 corresponde al promedio de los "
       "1.990 proveedores segmentados. Elaboración propia.")
p(doc, "Los grupos tienen una lectura de negocio directa:")
for nombre, texto in [
    ("Generalistas de alto volumen (450).", "Ofertan en muchos segmentos e instituciones (mediana "
     "de 104 líneas en 7 segmentos) y ganan alrededor de una de cada tres líneas. Son el "
     "23 % de los proveedores segmentados y reciben el 40,6 % del monto adjudicado."),
    ("Competidores focalizados (653).", "Se concentran en pocos segmentos, enfrentan más "
     "competencia (3,6 competidores por línea) y tienen el ticket medio más alto (₡2,4 millones "
     "por línea ganada)."),
    ("Nicho con poca competencia (502).", "Ganan casi todo lo que ofertan porque compiten en "
     "líneas con menos de un competidor en promedio. Es evidencia a nivel de proveedor de la "
     "hipótesis 3: existen espacios de baja competencia que una parte del mercado ya aprovecha."),
    ("Sin adjudicaciones (385).", "Ofertan en las líneas más disputadas (4 competidores) y, con "
     "al menos cinco líneas resueltas, todavía no ganan ninguna. Es el perfil al que la "
     "herramienta puede aportar más, al orientarlo hacia oportunidades con menos competencia."),
]:
    par = doc.add_paragraph(style="List Bullet")
    par.add_run(nombre + " ").bold = True
    par.add_run(texto)
p(doc, "Los dos primeros componentes principales explican el 61 % de la varianza. El primero "
       "resume la amplitud del proveedor (volumen, segmentos e instituciones) y el segundo "
       "opone el éxito a la competencia. En ese plano, los grupos aparecen bien separados "
       "(Figura 4).")
figura(doc, 4, "Grupos proyectados en los dos primeros componentes principales",
       "fig4_pca_grupos.png", "Cada panel resalta un grupo sobre el resto (en gris). Elaboración propia.",
       ancho=16)

h(doc, "Validación externa: ¿el tamaño de empresa explica los perfiles?", level=2)
p(doc, "El tamaño de empresa no se usó para formar los grupos, lo que permite usarlo como "
       "validación externa. La composición por tamaño es muy parecida en los cuatro grupos "
       "(Figura 5). La prueba chi-cuadrado de independencia no es significativa al 5 % "
       "(χ² = 15,3; gl = 9; p = 0,082) y la asociación es despreciable (V de Cramér = 0,05). Las "
       "MIPYMES (microemprendedores, pequeñas y medianas) están presentes en proporciones "
       "similares tanto entre los ganadores de nicho como entre quienes no han ganado.")
figura(doc, 5, "Composición por tamaño de empresa dentro de cada grupo", "fig5_tamano_por_grupo.png",
       "Elaboración propia.")
p(doc, "Este resultado apoya el planteamiento central del TFM: la desventaja de las MIPYMES no se "
       "explica por su tamaño, sino por dónde y contra quién eligen competir. Esa decisión "
       "depende de información, que es lo que la herramienta pretende proveer.")

h(doc, "Mapa de oportunidades por segmento de producto", level=2)
p(doc, "A nivel de mercado, se cruzó para cada segmento de la clasificación UNSPSC de SICOP la "
       "demanda (líneas publicadas) con la competencia (ofertas promedio por línea). Once "
       "segmentos se ubican en el cuadrante de alta demanda y baja competencia. Entre ellos "
       "están Equipo médico, accesorios e insumos; Servicios de transporte, almacenamiento y "
       "correo; Instrumentos de laboratorio; y Servicios de ingeniería, investigación y "
       "tecnología (Figura 6).")
figura(doc, 6, "Demanda y competencia por segmento UNSPSC de SICOP", "fig6_mapa_oportunidades.png",
       "Solo segmentos con al menos 100 líneas publicadas en procedimientos con ofertas "
       "registradas. Líneas discontinuas: medianas. Elaboración propia.", ancho=16)

h(doc, "Análisis complementarios", level=2)
p(doc, "La Figura 7 muestra la silueta de cada proveedor. Ningún grupo concentra el problema: "
       "la silueta media por grupo va de 0,21 (Competidores focalizados) a 0,35 (Sin "
       "adjudicaciones), y solo el 3,2 % de los proveedores de nicho y el 1,4 % de los "
       "focalizados tienen silueta negativa, es decir, quedarían mejor en otro grupo. La "
       "partición es coherente para casi todos los proveedores.")
figura(doc, 7, "Diagrama de silueta de la solución k = 4", "fig7_silueta.png",
       "Cada franja horizontal es un proveedor, ordenado dentro de su grupo. Elaboración propia.")
p(doc, "La Figura 8 muestra la dispersión dentro de cada grupo, que la tabla de medianas oculta. "
       "La tasa de éxito y el número de competidores separan con claridad al grupo de nicho y "
       "al grupo sin adjudicaciones, mientras que el volumen separa a los generalistas. El "
       "monto por línea ganada se solapa entre los tres grupos que ganan; por eso describe el "
       "tamaño del negocio y no define el perfil.")
figura(doc, 8, "Distribución de las variables clave por grupo", "fig8_cajas_por_grupo.png",
       "Diagramas de caja sin valores atípicos; escalas logarítmicas en volumen y monto. "
       "Elaboración propia.", ancho=16)
p(doc, "Por último, se examinó si el precio decide la adjudicación. En las líneas con dos o más "
       "ofertas con precio, la oferta ganadora fue la más barata en el 56 % de los casos, la "
       "segunda en el 27 % y la tercera o más cara en el 17 % (Figura 9). El precio pesa, pero "
       "no decide solo: en casi la mitad de las líneas intervienen otros criterios, coherentes "
       "con la Compra Pública Estratégica descrita en el marco teórico. Para el proveedor, esto "
       "significa que competir solo en precio no basta y que conocer cómo adjudica cada "
       "institución tiene valor, que es precisamente lo que ofrece el caso de uso 1.")
figura(doc, 9, "Posición en precio de la oferta ganadora", "fig9_posicion_precio_ganador.png",
       "Líneas resueltas con al menos dos ofertas con precio convertido a colones. "
       "Elaboración propia.")

h(doc, "Uso en la aplicación", level=2)
p(doc, "El escalador, el modelo KMeans y la asignación de cada proveedor se exportan desde el "
       "cuaderno y los lee la página «Caracterización de proveedores» de la aplicación "
       "Streamlit. Esa página muestra los cuatro perfiles, permite buscar un proveedor y "
       "compararlo con la mediana de su grupo, y presenta el mapa de oportunidades. Así, el "
       "análisis no supervisado deja de ser un ejercicio aislado y se convierte en una "
       "funcionalidad del producto.")

h(doc, "Limitaciones y trabajo futuro", level=2)
for texto in [
    "Cobertura de ofertas: en la versión de los datos utilizada (24/09/2026), solo cerca del "
    "12 % de los procedimientos publicados tiene ofertas registradas, y la cobertura cae en los "
    "meses recientes. Los perfiles describen a los proveedores observados, no a todo el "
    "mercado. El hallazgo se reportó al equipo del pipeline; cuando se corrija, basta con "
    "volver a ejecutar el cuaderno.",
    "El enlace entre oferta y adjudicación no es completo: alrededor de 14.000 adjudicaciones "
    "no tienen una oferta asociada. Esto puede subestimar la tasa de éxito de algunos "
    "proveedores.",
    "La silueta es moderada (0,26): los perfiles son tendencias, no fronteras nítidas. En la "
    "aplicación se presentan como referencia, no como clasificación definitiva.",
    "El periodo cubre 20 meses. Con más historia se podrá estudiar si los proveedores cambian "
    "de perfil a lo largo del tiempo, lo que permitiría medir el efecto de usar la herramienta.",
]:
    doc.add_paragraph(texto, style="List Bullet")

h(doc, "Librerías utilizadas y justificación", level=2)
tabla(doc, 4, "Librerías externas empleadas en el análisis",
      ["Librería", "Uso", "Justificación"],
      [["duckdb", "Lectura de sicop.duckdb", "Motor del pipeline del grupo; no requiere servidor"],
       ["pandas / numpy", "Manipulación y transformaciones", "Estándar para datos tabulares"],
       ["scikit-learn", "StandardScaler, KMeans, PCA, métricas", "Implementaciones validadas y reproducibles"],
       ["scipy", "Prueba chi-cuadrado", "Contraste de independencia"],
       ["matplotlib", "Figuras", "Control fino del sistema visual común del grupo"]],
      "El enunciado exige justificar toda librería externa. Elaboración propia.")

referencias(doc, [
    "Davies, D. L., y Bouldin, D. W. (1979). A cluster separation measure. IEEE Transactions on "
    "Pattern Analysis and Machine Intelligence, PAMI-1(2), 224–227. "
    "https://doi.org/10.1109/TPAMI.1979.4766909",
    "Hubert, L., y Arabie, P. (1985). Comparing partitions. Journal of Classification, 2(1), "
    "193–218. https://doi.org/10.1007/BF01908075",
    "MacQueen, J. (1967). Some methods for classification and analysis of multivariate "
    "observations. En L. M. Le Cam y J. Neyman (Eds.), Proceedings of the Fifth Berkeley "
    "Symposium on Mathematical Statistics and Probability (Vol. 1, pp. 281–297). University of "
    "California Press.",
    "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, "
    "M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., "
    "Brucher, M., Perrot, M., y Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. "
    "Journal of Machine Learning Research, 12, 2825–2830.",
    "Rousseeuw, P. J. (1987). Silhouettes: A graphical aid to the interpretation and validation "
    "of cluster analysis. Journal of Computational and Applied Mathematics, 20, 53–65. "
    "https://doi.org/10.1016/0377-0427(87)90125-7",
])
doc.save(Path(__file__).parent / "Seccion_Asig7_No_Supervisado.docx")

# =====================================================================
# 2. TFM, segundo entregable — Definición de la aplicación
# =====================================================================
doc = documento()
h(doc, "Definición de la aplicación", level=1)
p(doc, "Propuesta de sección para el segundo avance del TFM (definición de la app). Redacción: "
       "André Plannerer. Los párrafos marcados con [DECISIÓN DEL GRUPO] requieren validación "
       "del grupo antes de integrarse.", cursiva=True)

h(doc, "Propósito y usuario", level=2)
p(doc, "La aplicación responde a la persona definida en el primer avance: el gerente comercial "
       "de una MIPYME que decide en qué carteles de SICOP participar. Su criterio de valor es "
       "aumentar la tasa de adjudicación por oferta presentada, y su mayor dificultad es no "
       "poder anticipar cuántos competidores tendrá ni qué rango de precio gana en una categoría "
       "e institución. Cada funcionalidad de la aplicación se justifica por su aporte a esa "
       "decisión.")

h(doc, "Arquitectura", level=2)
p(doc, "La solución tiene tres capas, todas basadas en tecnologías gratuitas:")
for texto in [
    "Captura y procesamiento. Un pipeline en Python, ejecutado cada día con GitHub Actions, "
    "descarga los archivos del Observatorio de Compra Pública, los carga en tablas de staging y "
    "construye el modelo dimensional (hechos de carteles, ofertas y adjudicaciones; dimensiones "
    "de instituciones, proveedores y productos). El resultado es un único archivo DuckDB "
    "publicado como release del repositorio.",
    "Modelos. Sobre ese archivo se entrena el modelo supervisado de probabilidad de "
    "adjudicación, que escribe sus predicciones en la tabla predicciones_adjudicacion, y la "
    "segmentación de proveedores (KMeans), cuya asignación se exporta para la aplicación.",
    "Presentación. Una aplicación Streamlit de tres páginas, una por caso de uso, lee el archivo "
    "DuckDB en modo solo lectura. Toda la lógica de acceso a datos está en un único módulo, de "
    "modo que cambiar el motor de base de datos no afecta a las páginas.",
]:
    doc.add_paragraph(texto, style="List Bullet")
p(doc, "[DECISIÓN DEL GRUPO] El primer avance menciona PostgreSQL como sistema de almacenamiento. "
       "Durante septiembre de 2026, el pipeline se migró a DuckDB por tres motivos: no requiere "
       "un servidor, lo que elimina costos y administración; el archivo completo (≈250 MB) puede "
       "versionarse y distribuirse como release; y permite ejecutar el pipeline en GitHub "
       "Actions sin infraestructura propia. Se propone documentar este cambio como una decisión "
       "de diseño coherente con el requisito de gratuidad planteado en la delimitación del "
       "alcance. El diseño dimensional se mantiene; solo cambia el motor.")

h(doc, "Funcionalidades por caso de uso", level=2)
tabla(doc, 1, "Páginas de la aplicación y su correspondencia con los casos de uso",
      ["Página", "Caso de uso", "Pregunta que responde", "Contenido"],
      [["Demanda institucional", "UC1 · Comportamiento de la demanda institucional",
        "¿Quién compra lo que vendo, cuánto, a qué precio y en cuánto tiempo?",
        "Filtro por segmento UNSPSC y ventana de meses; indicadores de carteles, monto, "
        "competencia, precio adjudicado frente al estimado y días hasta adjudicar; "
        "instituciones compradoras; ranking de adjudicatarios; evolución mensual; ofertas por "
        "línea; posición en precio de la oferta ganadora; distribución del precio adjudicado "
        "frente al estimado; reparto del monto por tamaño de proveedor; precios por producto; "
        "últimos carteles"],
       ["Caracterización de proveedores", "UC2 · Caracterización de proveedores",
        "¿Contra quién compito y a qué perfil me parezco?",
        "Cuatro perfiles de proveedor (segmentación KMeans); buscador de proveedor con "
        "comparación frente a su perfil (tabla y gráfico de percentiles); composición por tamaño; mapa de oportunidades por "
        "segmento"],
       ["Probabilidad de adjudicación", "UC3 · Predicción de adjudicación",
        "¿En cuáles de mis ofertas conviene concentrar el esfuerzo?",
        "Ofertas en curso del proveedor, ordenadas por la probabilidad estimada por el modelo "
        "y clasificadas en prioridad alta, media o baja"]],
      "Casos de uso según la Tabla 1 del primer avance. Elaboración propia.")
figura(doc, 1, "Página del caso de uso 1 (demanda institucional)", "captura_uc1_demanda.png",
       "Captura del prototipo con datos reales hasta el 29/09/2026. Elaboración propia.")
figura(doc, 2, "Caso de uso 1: competencia y precios en el segmento",
       "captura_uc1_competencia_precios.png",
       "Ofertas por línea, posición en precio de la oferta ganadora, precio adjudicado frente "
       "al estimado y reparto del monto por tamaño de proveedor. Elaboración propia.")
figura(doc, 3, "Página del caso de uso 2 (caracterización de proveedores)",
       "captura_uc2_proveedores.png", "Elaboración propia.")
figura(doc, 4, "Página del caso de uso 3 con un proveedor seleccionado",
       "captura_uc3_busqueda.png",
       "Ofertas en curso ordenadas por probabilidad y prioridad relativa. Elaboración propia.")

h(doc, "Decisiones de diseño", level=2)
for nombre, texto in [
    ("Una página por caso de uso.", "Cada página responde una sola pregunta del proveedor. Esto "
     "sigue el Modelo de Aceptación de Tecnología citado en el marco teórico (Davis, 1989): la "
     "facilidad de uso percibida es antecedente de la utilidad percibida."),
    ("Filtro por segmento de producto.", "El proveedor conoce su oferta por categoría, no por "
     "código. Por eso el punto de entrada es el segmento de la clasificación UNSPSC de SICOP, "
     "ordenado por volumen de demanda."),
    ("Precios relativos al estimado.", "Los precios absolutos de productos distintos no se "
     "pueden comparar. La razón entre el precio adjudicado y el estimado del cartel sí, y "
     "responde directamente a la pregunta «¿a qué precio se gana?»."),
    ("Todos los montos en colones.", "SICOP registra cada línea en su moneda original. La "
     "aplicación convierte los dólares con el tipo de cambio de la línea y excluye las demás "
     "monedas (menos del 1 % de las líneas) para no mezclar unidades."),
    ("Predicción como orden relativo.", "Mientras el modelo no esté calibrado, se muestra la "
     "prioridad relativa (tercio superior, medio o inferior) junto a la probabilidad, con un "
     "aviso explícito. Así se evita que el usuario tome el número como una certeza."),
    ("Sistema visual común.", "Todos los gráficos usan la misma paleta, validada para "
     "daltonismo, y ofrecen información al pasar el cursor. Son los mismos criterios que se "
     "usarán en el reporting (Asignatura 8) y en la presentación de defensa."),
]:
    par = doc.add_paragraph(style="List Bullet")
    par.add_run(nombre + " ").bold = True
    par.add_run(texto)

h(doc, "Publicación", level=2)
p(doc, "[DECISIÓN DEL GRUPO] Se propone publicar la aplicación en Streamlit Community Cloud "
       "(gratuito). La aplicación descargaría sicop.duckdb del release público del repositorio "
       "al iniciar, de modo que siempre muestre los datos del último ciclo del pipeline sin "
       "necesidad de un servidor de base de datos. Esta alternativa sustituye a Supabase, "
       "mencionado en versiones anteriores del documento.")

h(doc, "Justificación del cambio de extensión a herramienta web", level=2)
p(doc, "[DECISIÓN DEL GRUPO] La ficha aprobada describe una extensión de navegador, mientras que "
       "el primer avance ya presenta una herramienta web. Se propone justificar el cambio con "
       "tres argumentos. Primero, una extensión depende de la estructura de las páginas de "
       "SICOP, que el grupo no controla, mientras que la herramienta web depende solo de los "
       "datos abiertos del Observatorio. Segundo, una herramienta web no requiere instalación, "
       "lo que según el TAM reduce la barrera de adopción para usuarios con poca capacidad "
       "técnica. Tercero, la misma aplicación podrá integrarse en el futuro como panel lateral "
       "de una extensión, así que el cambio no cierra esa opción.")

referencias(doc, [
    "Davis, F. (1989). Perceived usefulness, perceived ease of use, and user acceptance of "
    "information technology. MIS Quarterly, 13(3), 319–340. https://doi.org/10.2307/249008 "
    "(ya incluida en la bibliografía del primer avance)",
])
doc.save(Path(__file__).parent / "Seccion_TFM_Definicion_App.docx")
print("docx generados")
