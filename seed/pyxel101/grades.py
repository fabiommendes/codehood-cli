"""
Nota final do curso `pyxel101`.

Pesos (README do curso): laboratórios 25%, Prova 1 20%, Prova 2 25% e projeto
final 30%. A prova de reposição substitui a menor nota entre as duas provas.
Aprovação: média de 50 ou mais e frequência de pelo menos 75%.
"""

from codehood.grades import Student

WEIGHTS = {"labs": 0.25, "prova1": 0.20, "prova2": 0.25, "projeto": 0.30}
PASSING_AVERAGE = 50.0
MIN_ATTENDANCE = 75.0


def exam_score(student: Student, slug: str) -> float:
    """Nota de 0 a 100 em uma prova, ou 0 se não houver nota."""
    result = student.exams.get(slug)
    if result is None or result.score is None:
        return 0.0
    return max(result.score, 0.0)


def number(student: Student, slug: str) -> float:
    """Valor numérico de uma coluna de `grades.csv`, ou 0 se vazio."""
    value = student.scores.get(slug)
    return float(value) if isinstance(value, int | float) else 0.0


def average(student: Student) -> float:
    """Média ponderada, já com a prova de reposição aplicada."""
    prova1 = exam_score(student, "prova1")
    prova2 = exam_score(student, "prova2")
    reposicao = exam_score(student, "prova-reposicao")
    if reposicao > min(prova1, prova2):
        if prova1 <= prova2:
            prova1 = reposicao
        else:
            prova2 = reposicao
    return (
        WEIGHTS["labs"] * number(student, "labs")
        + WEIGHTS["prova1"] * prova1
        + WEIGHTS["prova2"] * prova2
        + WEIGHTS["projeto"] * number(student, "projeto")
    )


def grade(student: Student) -> dict[str, float | str | None]:
    """Calcula o conceito final (aprovado ou reprovado) de um aluno."""
    if student.status == "dropped":
        return {"final": None}
    # A frequência não é uma coluna declarada: se `grades.csv` tiver a coluna
    # `frequencia` (0 a 100), ela vale; sem o dado, não reprova por falta.
    attendance = student.scores.get("frequencia")
    if isinstance(attendance, int | float) and attendance < MIN_ATTENDANCE:
        return {"final": "reprovado"}
    return {"final": "aprovado" if average(student) >= PASSING_AVERAGE else "reprovado"}
