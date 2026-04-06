"""10종 시드 데이터 범용성 검증 스크립트.

각 시드에 대해 전체 파이프라인을 실행하고 점수를 측정한다.
결과를 validation_results.tsv에 기록한다.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

SEEDS = [
    ("01_MCU스토리_시드데이터.txt", "엔터테인먼트(MCU)"),
    ("02_제조업_시드데이터.txt", "제조업(자동차공급망)"),
    ("03_지정학_시드데이터.txt", "정치/외교(한반도)"),
    ("04_금융시장_시드데이터.txt", "금융(글로벌금리)"),
    ("05_바이오의약_시드데이터.txt", "의료/바이오(신약)"),
    ("06_AI산업_시드데이터.txt", "기술(AI산업)"),
    ("07_에너지기후_시드데이터.txt", "환경/에너지(탄소중립)"),
    ("08_교육개혁_시드데이터.txt", "교육(구조개혁)"),
    ("09_부동산_시드데이터.txt", "부동산(시장역학)"),
    ("10_근대사_시드데이터.txt", "역사(개항~병합)"),
]

DATA_DIR = Path("data")
TESTER_DIR = Path("tester")
RESULTS_FILE = Path("validation_results.tsv")


def backup_data():
    """현재 data/ 디렉토리를 백업한다."""
    backup = DATA_DIR.parent / "data_backup"
    if backup.exists():
        shutil.rmtree(backup)
    if DATA_DIR.exists():
        shutil.copytree(DATA_DIR, backup)
    return backup


def restore_data(backup: Path):
    """백업에서 data/ 디렉토리를 복원한다."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    if backup.exists():
        shutil.copytree(backup, DATA_DIR)


def clear_data():
    """data/ 디렉토리의 실행 결과를 초기화한다."""
    for subdir in ["extraction", "snapshots", "analysis", "reports"]:
        p = DATA_DIR / subdir
        if p.exists():
            shutil.rmtree(p)
    # chunk_results 캐시도 초기화
    cache = DATA_DIR / "extraction" / "chunk_results"
    if cache.exists():
        shutil.rmtree(cache)


def run_pipeline(seed_path: Path, rounds: int = 5) -> tuple[float, dict]:
    """파이프라인을 실행하고 점수를 측정한다."""
    start = time.time()

    # 파이프라인 실행
    result = subprocess.run(
        [sys.executable, "main.py", "run", str(seed_path), "--rounds", str(rounds)],
        capture_output=True,
        text=True,
        timeout=3600,  # 60분 타임아웃
    )

    elapsed = time.time() - start

    if result.returncode != 0:
        return 0.0, {
            "error": result.stderr[-500:] if result.stderr else "unknown",
            "elapsed": elapsed,
        }

    # 점수 측정
    score_result = subprocess.run(
        [sys.executable, "score.py"],
        capture_output=True,
        text=True,
    )

    score = 0.0
    details = {"elapsed": elapsed}

    for line in score_result.stdout.strip().split("\n"):
        if line.startswith("SCORE="):
            score = float(line.split("=")[1])
        elif line.startswith("ENTITIES="):
            details["entities"] = int(line.split("=")[1])
        elif line.startswith("RELATIONSHIPS="):
            details["relationships"] = int(line.split("=")[1])
        elif line.startswith("REPORT_WORDS="):
            details["report_words"] = int(line.split("=")[1])
        elif line.startswith("QUALITY_BONUS="):
            details["quality_bonus"] = float(line.split("=")[1])

    return score, details


def validate_report(report_dir: Path) -> list[str]:
    """보고서 품질을 검증한다."""
    issues = []
    reports = list(report_dir.glob("*.md"))
    if not reports:
        issues.append("보고서 파일 없음")
        return issues

    report = reports[0].read_text(encoding="utf-8")

    required = [
        "Executive Summary",
        "인과 분석",
        "구조 분석",
        "시스템 다이내믹스",
        "시나리오 분석",
        "핵심 엔티티 프로파일",
        "리스크 매트릭스",
        "전략적 권고사항",
    ]

    for section in required:
        if section not in report:
            issues.append(f"섹션 누락: {section}")

    words = len(report.split())
    if words < 3000:
        issues.append(f"보고서 너무 짧음: {words}단어")

    return issues


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    specific = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"=== ComadEye 범용성 검증 (rounds={rounds}) ===\n")

    # 결과 파일 헤더
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write("seed\tdomain\tscore\tentities\trels\twords\tquality\ttime_sec\tissues\n")

    # 현재 데이터 백업
    backup = backup_data()

    seeds_to_run = SEEDS
    if specific:
        seeds_to_run = [(s, d) for s, d in SEEDS if specific in s or specific in d]

    for seed_file, domain in seeds_to_run:
        seed_path = TESTER_DIR / seed_file

        if not seed_path.exists():
            print(f"[SKIP] {seed_file} — 파일 없음")
            with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{seed_file}\t{domain}\t0\t0\t0\t0\t0\t0\tFILE_NOT_FOUND\n")
            continue

        print(f"[RUN] {domain} ({seed_file})")
        clear_data()

        try:
            score, details = run_pipeline(seed_path, rounds)
            issues = validate_report(DATA_DIR / "reports") if score > 0 else ["파이프라인 실패"]
            issue_str = "; ".join(issues) if issues else "OK"

            entities = details.get("entities", 0)
            rels = details.get("relationships", 0)
            words = details.get("report_words", 0)
            quality = details.get("quality_bonus", 0)
            elapsed = details.get("elapsed", 0)

            status = "PASS" if score > 0 and not issues else "FAIL"
            print(
                f"  [{status}] SCORE={score:.1f} | "
                f"E={entities} R={rels} W={words} | "
                f"Quality={quality:.0f}/350 | "
                f"{elapsed:.0f}s | {issue_str}"
            )

            with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{seed_file}\t{domain}\t{score:.1f}\t{entities}\t"
                    f"{rels}\t{words}\t{quality:.0f}\t{elapsed:.0f}\t{issue_str}\n"
                )

        except subprocess.TimeoutExpired:
            print("  [TIMEOUT] 60분 초과")
            with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{seed_file}\t{domain}\t0\t0\t0\t0\t0\t3600\tTIMEOUT\n")
        except Exception as e:
            print(f"  [ERROR] {e}")
            with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{seed_file}\t{domain}\t0\t0\t0\t0\t0\t0\t{str(e)[:50]}\n")

    # 데이터 복원
    restore_data(backup)
    shutil.rmtree(backup, ignore_errors=True)

    # 최종 요약
    print("\n=== 검증 결과 요약 ===\n")
    if RESULTS_FILE.exists():
        print(RESULTS_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
