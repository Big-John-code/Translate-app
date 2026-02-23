# Glossary of technical terms for Fundamentals of Software Architecture
# Terms in KEEP_AS_IS will be preserved in English
# Terms in TRANSLATE will be replaced with Ukrainian equivalents

KEEP_AS_IS = {
    # Core role terms — keep in English per user preference
    "software architect", "software architecture", "software engineering",
    "software developer", "software development",
    # Infrastructure & Tools
    "API", "REST", "GraphQL", "gRPC", "HTTP", "HTTPS", "TCP", "UDP",
    "Docker", "Kubernetes", "CI/CD", "DevOps", "GitOps",
    "SQL", "NoSQL", "MongoDB", "PostgreSQL", "Redis", "Kafka",
    "AWS", "GCP", "Azure", "SaaS", "PaaS", "IaaS",
    # Patterns
    "microservices", "monolith", "event-driven", "pipeline",
    "SOLID", "DDD", "TDD", "BDD",
    # Abbreviations
    "ADR", "SLA", "SLO", "SLI", "RTO", "RPO",
}

# Ukrainian translations for key architecture terms
# Format: "english term (case-insensitive)": "ukrainian translation"
TECH_GLOSSARY = {
    # Core roles (software architect/architecture залишаються англійськими)
    "architect": "архітектор",
    "developer": "розробник",
    "stakeholder": "зацікавлена сторона",
    "stakeholders": "зацікавлені сторони",

    # Architecture concepts
    "architecture characteristics": "архітектурні характеристики",
    "architecture characteristic": "архітектурна характеристика",
    "architectural quantum": "архітектурний квант",
    "architectural quanta": "архітектурні кванти",
    "fitness function": "фітнес-функція",
    "fitness functions": "фітнес-функції",
    "bounded context": "обмежений контекст",
    "bounded contexts": "обмежені контексти",
    "component": "компонент",
    "components": "компоненти",
    "deployment unit": "одиниця розгортання",

    # Quality attributes
    "scalability": "масштабованість",
    "availability": "доступність",
    "reliability": "надійність",
    "maintainability": "зручність супроводу",
    "testability": "тестованість",
    "deployability": "придатність до розгортання",
    "agility": "гнучкість",
    "elasticity": "еластичність",
    "performance": "продуктивність",
    "security": "безпека",
    "observability": "спостережуваність",
    "fault tolerance": "відмовостійкість",
    "recoverability": "відновлюваність",

    # Structural concepts
    "coupling": "зв'язаність",
    "cohesion": "зчепленість",
    "modularity": "модульність",
    "abstraction": "абстракція",
    "encapsulation": "інкапсуляція",
    "connascence": "конасценція",
    "afferent coupling": "доцентрова зв'язаність",
    "efferent coupling": "відцентрова зв'язаність",
    "abstractness": "абстрактність",
    "instability": "нестабільність",
    "distance from the main sequence": "відстань від головної послідовності",

    # Architecture styles
    "layered architecture": "шарувата архітектура",
    "microkernel architecture": "мікроядерна архітектура",
    "service-based architecture": "сервісно-орієнтована архітектура",
    "event-driven architecture": "подієво-орієнтована архітектура",
    "space-based architecture": "просторово-орієнтована архітектура",
    "pipeline architecture": "конвеєрна архітектура",
    "orchestration-driven service-oriented architecture": "оркестраційно-керована сервісно-орієнтована архітектура",
    "microservices architecture": "мікросервісна архітектура",
    "big ball of mud": "великий клубок бруду",

    # Patterns
    "trade-off": "компроміс",
    "trade-offs": "компроміси",
    "anti-pattern": "антипатерн",
    "anti-patterns": "антипатерни",
    "design pattern": "патерн проєктування",
    "design patterns": "патерни проєктування",
    "broker topology": "топологія брокера",
    "mediator topology": "топологія медіатора",
    "orchestration": "оркестрація",
    "choreography": "хореографія",
    "saga": "сага",
    "sagas": "саги",

    # Engineering practices
    "continuous delivery": "безперервне постачання",
    "continuous integration": "безперервна інтеграція",
    "continuous deployment": "безперервне розгортання",
    "refactoring": "рефакторинг",
    "technical debt": "технічний борг",
    "code review": "перегляд коду",
    "pull request": "запит на злиття",

    # Decision-making
    "architecture decision record": "запис архітектурного рішення",
    "architecture decision records": "записи архітектурних рішень",
    "risk assessment": "оцінка ризиків",
    "risk matrix": "матриця ризиків",
    "risk storming": "штурм ризиків",

    # Teams & processes
    "agile": "гнучка методологія (Agile)",
    "scrum": "Scrum",
    "team topology": "топологія команди",
    "domain-driven design": "предметно-орієнтоване проєктування (DDD)",
    "extreme programming": "екстремальне програмування (XP)",
}


def build_glossary_note() -> str:
    """Returns a markdown glossary section for the output document."""
    lines = ["## Глосарій технічних термінів\n"]
    lines.append("| Англійський термін | Українське значення |")
    lines.append("|---|---|")
    for en, ua in sorted(TECH_GLOSSARY.items()):
        lines.append(f"| {en} | {ua} |")
    return "\n".join(lines)
