"""ComadEye CLI — Ontology-Native Prediction Simulation Engine"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from comad_eye.config import load_settings
from comad_eye.logger import setup_logger

app = typer.Typer(
    name="comadeye",
    help="ComadEye — Ontology-Native Prediction Simulation Engine",
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(
    seed: Path = typer.Argument(..., help="시드 데이터 파일 경로 (.txt)"),
    rounds: int = typer.Option(10, "--rounds", "-r", help="시뮬레이션 라운드 수"),
    output: Path = typer.Option(
        Path("data/reports"), "--output", "-o", help="리포트 출력 디렉토리"
    ),
    skip_report: bool = typer.Option(
        False, "--skip-report", help="리포트 생성 생략"
    ),
):
    """시드 데이터 → 시뮬레이션 → 분석 → 리포트 전체 파이프라인 실행."""
    settings = load_settings()
    setup_logger(settings.logging)

    if not seed.exists():
        console.print(f"[red]파일을 찾을 수 없습니다: {seed}[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold cyan]ComadEye[/bold cyan]\n"
        f"Seed: {seed.name}\n"
        f"Rounds: {rounds}",
        title="Ontology-Native Prediction Engine",
    ))

    settings.simulation.max_rounds = rounds

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Phase 1: Ingestion
        task = progress.add_task("Ingestion — 시드 데이터 처리", total=None)
        seed_text = seed.read_text(encoding="utf-8")
        chunks, ontology, _usage = _run_ingestion(seed_text, settings)
        progress.update(task, completed=True)

        # Phase 2: Graph Loading
        task = progress.add_task("Graph — Neo4j 로딩", total=None)
        client = _run_graph_loading(ontology, settings)
        progress.update(task, completed=True)

        # Phase 3: Community Detection
        task = progress.add_task("Community — 커뮤니티 탐지", total=None)
        _run_community_detection(client, settings)  # usage stats discarded in CLI
        progress.update(task, completed=True)

        # Phase 4: Simulation
        task = progress.add_task("Simulation — 시뮬레이션 실행", total=None)
        sim_result = _run_simulation(client, ontology, settings)
        progress.update(task, completed=True)

        # Phase 5: Analysis + Lens Deep Filters
        task = progress.add_task("Analysis — 6개 분석공간 + 렌즈 딥 필터", total=None)
        _run_analysis(client, settings, seed_text=seed_text)
        progress.update(task, completed=True)

        # Phase 6: Report
        if not skip_report:
            task = progress.add_task("Report — 리포트 생성", total=None)
            report_path, _usage = _run_report(
                seed_text, sim_result, output, settings
            )
            progress.update(task, completed=True)
            console.print(f"\n[green]리포트 생성 완료:[/green] {report_path}")

    console.print(Panel(
        f"[bold green]파이프라인 완료[/bold green]\n"
        f"Rounds: {sim_result.get('total_rounds', rounds)} | "
        f"Events: {sim_result.get('total_events', 0)} | "
        f"Actions: {sim_result.get('total_actions', 0)}",
        title="Done",
    ))


@app.command()
def qa(
    analysis_dir: Path = typer.Option(
        Path("data/analysis"), "--analysis-dir", "-a", help="분석 결과 디렉토리"
    ),
):
    """대화형 Q&A 세션을 시작한다."""
    settings = load_settings()
    setup_logger(settings.logging)

    from comad_eye.graph.neo4j_client import Neo4jClient
    from comad_eye.narration.qa_session import QASession
    from comad_eye.llm_client import LLMClient

    console.print(Panel(
        "[bold cyan]ComadEye Q&A Session[/bold cyan]\n"
        "Type 'exit' to quit, 'reset' to clear history.",
        title="Q&A",
    ))

    client = Neo4jClient(settings=settings.neo4j)
    llm = LLMClient(settings=settings.llm)

    session = QASession(
        graph=client,
        llm=llm,
        analysis_dir=analysis_dir,
    )

    # 이전 세션 복원
    restored = session.load_session()
    if restored:
        console.print(f"[dim]이전 대화 {restored}턴 복원됨[/dim]")

    try:
        while True:
            question = console.input("\n[bold]You:[/bold] ").strip()

            if not question:
                continue
            if question.lower() == "exit":
                break
            if question.lower() == "reset":
                session.reset()
                console.print("[yellow]대화 이력이 초기화되었습니다.[/yellow]")
                continue

            with console.status("분석 중..."):
                answer = session.ask(question)

            console.print(f"\n[bold green]ComadEye:[/bold green]\n{answer}")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        session.save_session()
        client.close()
        console.print("\n[dim]Q&A 세션 종료 (대화 저장됨)[/dim]")


@app.command()
def analyze(
    snapshot_dir: Path = typer.Option(
        Path("data/snapshots"), "--snapshots", "-s", help="스냅샷 디렉토리"
    ),
    output_dir: Path = typer.Option(
        Path("data/analysis"), "--output", "-o", help="분석 결과 출력 디렉토리"
    ),
):
    """스냅샷 데이터에 대해 6개 분석공간을 실행한다."""
    settings = load_settings()
    setup_logger(settings.logging)

    from comad_eye.analysis.aggregator import AnalysisAggregator
    from comad_eye.analysis.base import SimulationData
    from comad_eye.graph.neo4j_client import Neo4jClient

    client = Neo4jClient(settings=settings.neo4j)

    try:
        data = SimulationData.from_snapshots(snapshot_dir, graph=client)
        aggregator = AnalysisAggregator(data, output_dir)
        result = aggregator.run_all()
        console.print(f"[green]분석 완료: {len(result.get('key_findings', []))}개 핵심 발견[/green]")
    finally:
        client.close()


@app.command()
def report(
    seed: Path = typer.Argument(..., help="시드 데이터 파일 경로"),
    analysis_dir: Path = typer.Option(
        Path("data/analysis"), "--analysis-dir", "-a", help="분석 결과 디렉토리"
    ),
    output_dir: Path = typer.Option(
        Path("data/reports"), "--output", "-o", help="리포트 출력 디렉토리"
    ),
):
    """분석 결과에서 리포트를 생성한다."""
    settings = load_settings()
    setup_logger(settings.logging)

    from comad_eye.narration.report_generator import ReportGenerator
    from comad_eye.llm_client import LLMClient

    llm = LLMClient(settings=settings.llm)
    generator = ReportGenerator(llm, analysis_dir, output_dir)
    seed_text = seed.read_text(encoding="utf-8") if seed.exists() else ""

    path = generator.generate(seed_excerpt=seed_text[:500])
    console.print(f"[green]리포트 생성 완료:[/green] {path}")


# --- Internal Pipeline Functions (delegate to pipeline.orchestrator) ---
# Kept as thin wrappers for backward compatibility with any external scripts.

from comad_eye.pipeline.orchestrator import (
    run_ingestion as _run_ingestion,
    run_graph_loading as _run_graph_loading,
    run_community_detection as _run_community_detection,
    run_simulation as _run_simulation,
    run_analysis as _run_analysis,
    run_report as _run_report,
)


if __name__ == "__main__":
    app()
