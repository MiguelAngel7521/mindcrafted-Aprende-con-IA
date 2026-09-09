"""Textos en español para los juegos y la plataforma del curso."""

DEFAULT_LOCALE = "es"

UI_STRINGS: dict[str, dict[str, object]] = {
    "es": {
        "lang": "es",
        "musicTitle": "Música",
        "sfxTitle": "Efectos",
        "clickToContinue": "▼ Haz clic para continuar",
        "nameLabel": "Tu nombre:",
        "namePlaceholder": "Ingresa tu nombre",
        "startGame": "♥ Iniciar juego",
        "startHint": "Haz clic para empezar (con audio)",
        "chapters": "capítulos",
        "defaultPlayer": "Explorador",
        "endTitle": "✿ ¡Felicidades, {player}! ✿",
        "endSub": "{player}, ¡completaste los {total} capítulos!",
        "endMastered": "Mecánicas y conocimientos dominados:",
        "playAgain": "♥ Jugar de nuevo",
        "nextGame": "Siguiente juego →",
        "loadError": "Error al cargar",
        "skip": "Saltar →",
        "promptLang": "Todo el contenido de texto debe estar únicamente en español, sin mezclar otros idiomas",
        "continue": "Continuar →",
        "complete": "✿ ¡Completado!",
        "progress": "Progreso",
        "score": "Puntuación",
        "collected": "Recolectado",
        "ready": "Listo...",
        "tooSlow": "¡Demasiado lento!",
        "accuracy": "Precisión",
        "avgRT": "Tiempo de reacción prom.",
        "decision": "Decisión",
        "budget": "Presupuesto",
        "effect": "Efecto",
        "phase": "Fase",
        "cost": "Costo",
        "round": "Ronda",
        "satisfaction": "Satisfacción prom.",
        "visited": "Visitado",
        "clickReveal": "Haz clic para revelar",
        "original": "Original",
        "target": "Objetivo",
        "operations": "Operaciones",
        "matchSuccess": "✿ ¡Coincidencia exitosa!",
        "collectionDone": "✿ ¡Colección completa!",
        "journeyDone": "✿ ¡Viaje completado!",
        "reactionDone": "✿ ¡Prueba de reacción completa!",
        "planDone": "✿ ¡Planificación completa!",
        "planNeedsWork": "La estrategia necesita mejoras",
        "negotiationDone": "✿ ¡Negociación completa!",
        "required": "Requerido",
        "used": "Usado",
        "concept": "Concepto",
        "description": "Descripción",
        "matchedLabel": "Emparejado",
        "selectCategory": "Selecciona la categoría correcta",
        "accuracyLabel": "Precisión",
        "correct": "¡Correcto!",
        "shouldBe": "Debería ser",
        "stepLabel": "Paso",
        "placedLabel": "Colocado",
        "componentLabel": "Componente",
        "assembledLabel": "Ensamblado",
        "goalLabel": "Meta",
        "selectReaction": "Selecciona una reacción",
        "correctFeedback": "¡Correcto!",
        "incorrectFeedback": "Incorrecto.",
        "discovered": "Descubierto",
        "selectTarget": "Selecciona el objetivo",
        "selected": "Seleccionado",
        "isTarget": "Objetivo",
        "confirm": "Confirmar",
        "notTarget": "No es el objetivo, ¡intenta de nuevo!",
        "budgetLimit": "Límite de presupuesto",
        "predicted": "Predicho",
        "ideal": "Ideal",
        "yourPrediction": "Tu predicción vs curva ideal",
        "backToCourse": "Volver al curso",
        "aiDisclaimer": "El contenido generado por IA puede contener errores; verifícalo. · ahafrog",
        "levelUp": "¡SUBISTE DE NIVEL!",
        "chapter": "Capítulo",
        "earned": "Ganado",
        "stars": "Estrellas",
        "levelNames": ["✦ Novato", "✦✦ Aprendiz", "✦✦✦ Erudito", "✧ Experto", "✧✧ Maestro", "✧✧✧ Leyenda"],
        "coins": "Monedas de conocimiento",
        "inventory": "Inventario",
        "inventoryTitle": "Coleccionables",
        "inventoryEmpty": "Tu inventario está vacío. ¡Sigue explorando!",
        "petMoodHappy": "Feliz",
        "petMoodNeutral": "Tranquilo",
        "petMoodSleepy": "Soñoliento",
        "continueBtn": "Continuar →",
        "chapterComplete": "¡Capítulo completado!",
        "shareGame": "Compartir juego",
        "shareCopyLink": "Copiar enlace",
        "shareWeChat": "WeChat",
        "shareXiaohongshu": "Xiaohongshu",
        "shareLinkedIn": "LinkedIn",
        "shareTwitter": "X / Twitter",
        "shareFacebook": "Facebook",
        "shareInstagram": "Instagram",
        "shareCopied": "¡Enlace copiado!",
        "grade": "Calificación",
        "start": "Comenzar",
        "xpUnit": "EXP",
        "levelPrefix": "Nivel",
        "chapterFormat": "Capítulo {n}",
        "retry": "Reintentar",
        "scoreUnit": "pts",
        "reportSubmitted": "Reporte enviado. Gracias por ayudarnos a mejorar.",
    }
}

COURSE_PAGE_STRINGS: dict[str, dict[str, str]] = {
    "es": {
        "lang": "es",
        "allCourses": "← Todos los cursos",
        "login": "INGRESAR",
        "signup": "REGISTRARSE",
        "badge": "♦ APRENDIZAJE BASADO EN JUEGOS",
        "statGames": "JUEGOS",
        "statTime": "TIEMPO",
        "statLevel": "NIVEL",
        "statDone": "COMPLETADO",
        "startLearning": "♥ EMPEZAR A APRENDER",
        "subscribe": "★ SUSCRIBIRSE",
        "objectivesTitle": "✦ Lo que aprenderás",
        "objectivesDesc": "Domina estos conceptos clave a través del juego interactivo",
        "lessonsTitle": "◈ Lecciones del curso",
        "lessonsDesc": "Cada lección es una experiencia de juego interactiva completa",
        "btnStart": "▶ INICIAR",
        "btnLocked": "🔒 BLOQUEADO",
        "footerBuilt": "Creado con ahafrog — Aprendizaje con IA y juegos",
        "footerLessons": "Lecciones",
        "dashboard": "Mi Panel",
    }
}

LOCALE_NAMES: dict[str, str] = {"es": "Español"}


def get_ui_strings(locale: str = DEFAULT_LOCALE) -> dict:
    """Devuelve una copia para evitar mutaciones entre juegos."""
    return dict(UI_STRINGS[DEFAULT_LOCALE])


def get_course_page_strings(locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    return dict(COURSE_PAGE_STRINGS[DEFAULT_LOCALE])


def get_prompt_lang_instruction(locale: str = DEFAULT_LOCALE) -> str:
    return str(UI_STRINGS[DEFAULT_LOCALE]["promptLang"])


def extract_locale_content(config: dict, script: list) -> dict:
    """Extrae el contenido en español usado por el reproductor empaquetado."""
    meta = {
        "title": config.get("title", ""),
        "subtitle": config.get("subtitle", ""),
        "description": config.get("description", ""),
        "defaultPlayerName": config.get("defaultPlayerName", ""),
    }
    characters = {
        cid: cinfo["name"]
        for cid, cinfo in config.get("characters", {}).items()
        if isinstance(cinfo, dict) and "name" in cinfo
    }
    dialogs = [
        [index, command.get("name", ""), command.get("text", "")]
        for index, command in enumerate(script)
        if isinstance(command, dict) and command.get("type") == "dialog"
    ]
    minigames = {
        key: _strip_non_text(value)
        for key, value in config.get("minigames", {}).items()
        if isinstance(value, dict)
    }
    end_screen = {}
    mechanics = config.get("endScreen", {}).get("mechanics", [])
    if mechanics:
        end_screen["mechanics"] = [
            {"mechanic": item.get("mechanic", ""), "knowledge": item.get("knowledge", "")}
            for item in mechanics
            if isinstance(item, dict)
        ]
    return {
        "locale": DEFAULT_LOCALE,
        "meta": meta,
        "characters": characters,
        "dialogs": dialogs,
        "minigames": minigames,
        "endScreen": end_screen,
        "ui": config.get("ui", get_ui_strings()),
    }


def _strip_non_text(value):
    if isinstance(value, list):
        return [_strip_non_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_non_text(item) for key, item in value.items()}
    return value
