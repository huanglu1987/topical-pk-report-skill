from __future__ import annotations

import argparse
from pathlib import Path

from .demo import init_demo
from .evidence import fetch_cde_sources, fetch_fda_label, fetch_pubchem
from .report import generate_report
from .sampling import recommend_sampling
from .simulation import run_exposure_simulation
from .one_click import run_from_basic_input


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pktool",
        description="外用制剂系统暴露预测与 PK 采血点建模工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-demo", help="生成示例输入和目录结构")
    init_parser.add_argument("--force", action="store_true", help="覆盖已存在的示例文件")

    pubchem_parser = subparsers.add_parser("fetch-pubchem", help="通过 PubChem PUG REST 检索分子属性")
    pubchem_parser.add_argument("--name", required=True, help="化合物名称")
    pubchem_parser.add_argument("--output-dir", default="data/evidence_cache")

    fda_parser = subparsers.add_parser("fetch-fda", help="通过 openFDA drug label 检索标签线索")
    fda_parser.add_argument("--ingredient", required=True, help="通用名或活性成分名称")
    fda_parser.add_argument("--limit", type=int, default=5)
    fda_parser.add_argument("--output-dir", default="data/evidence_cache")

    cde_parser = subparsers.add_parser("fetch-cde", help="检索/登记 CDE 官方来源")
    cde_parser.add_argument("--keyword", required=True, help="关键词")
    cde_parser.add_argument("--url", help="可选：手动登记 CDE 官方 URL")
    cde_parser.add_argument("--output-dir", default="data/evidence_cache")

    sim_parser = subparsers.add_parser("simulate-exposure", help="运行系统暴露蒙特卡洛模拟")
    sim_parser.add_argument("--compound", required=True)
    sim_parser.add_argument("--reference", required=True)
    sim_parser.add_argument("--product", required=True)
    sim_parser.add_argument("--design", default="data/study_design.yaml")
    sim_parser.add_argument("--output-dir", default="outputs")
    sim_parser.add_argument("--n-simulations", type=int)

    sampling_parser = subparsers.add_parser("recommend-sampling", help="基于模拟结果推荐采血点")
    sampling_parser.add_argument("--simulation", default="outputs/simulation_results.csv")
    sampling_parser.add_argument("--design", default="data/study_design.yaml")
    sampling_parser.add_argument("--output", default="outputs/sampling_recommendation.csv")

    report_parser = subparsers.add_parser("report", help="生成 Markdown/Excel 报告")
    report_parser.add_argument("--simulation", default="outputs/simulation_results.csv")
    report_parser.add_argument("--metrics", default="outputs/simulation_metrics.csv")
    report_parser.add_argument("--sampling", default="outputs/sampling_recommendation.csv")
    report_parser.add_argument("--evidence-manifest", default="data/evidence_cache/evidence_manifest.csv")
    report_parser.add_argument("--format", default="md,xlsx")
    report_parser.add_argument("--reports-dir", default="outputs/reports")

    run_parser = subparsers.add_parser("run-report", help="从简洁 YAML 输入一键生成系统暴露与采血点报告")
    run_parser.add_argument("--input", required=True, help="品种基础信息 YAML")
    run_parser.add_argument("--output-root", default="runs", help="每次运行的输出根目录")
    run_parser.add_argument("--no-fetch", action="store_true", help="不运行 PubChem/openFDA/CDE 在线检索")
    run_parser.add_argument("--purpose", choices=["exploratory", "must_max_use", "be_bridging"], help="覆盖 YAML 中的主采血目的")
    run_parser.add_argument("--variability-preset", choices=["low", "medium", "high", "custom"], help="覆盖 YAML 中的变异度 preset")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-demo":
        created = init_demo(Path("."), force=args.force)
        if created:
            print("Created demo files:")
            for path in created:
                print(f"- {path}")
        else:
            print("Demo files already exist. Use --force to overwrite.")
        return 0

    if args.command == "fetch-pubchem":
        result = fetch_pubchem(args.name, output_dir=args.output_dir)
        print(f"PubChem status: {'ok' if result.get('ok') else 'not ok'}")
        print(f"Cache: {args.output_dir}")
        return 0

    if args.command == "fetch-fda":
        result = fetch_fda_label(args.ingredient, output_dir=args.output_dir, limit=args.limit)
        print(f"FDA label records: {result.get('labels_found', 0)}")
        print(f"Cache: {args.output_dir}")
        return 0

    if args.command == "fetch-cde":
        result = fetch_cde_sources(args.keyword, output_dir=args.output_dir, url=args.url)
        print(f"CDE sources registered: {len(result.get('records', []))}")
        print(f"Cache: {args.output_dir}")
        return 0

    if args.command == "simulate-exposure":
        result = run_exposure_simulation(
            compound_path=args.compound,
            reference_path=args.reference,
            product_path=args.product,
            design_path=args.design,
            output_dir=args.output_dir,
            n_simulations=args.n_simulations,
        )
        print(f"Simulation complete: {result['n_simulations']} runs")
        print(f"- {result['simulation_results']}")
        print(f"- {result['simulation_metrics']}")
        print(f"- {result['simulation_summary']}")
        for warning in result.get("warnings", []):
            print(f"Warning: {warning}")
        return 0

    if args.command == "recommend-sampling":
        output = recommend_sampling(args.simulation, design_path=args.design, output_path=args.output)
        print(f"Sampling recommendation: {output}")
        return 0

    if args.command == "report":
        outputs = generate_report(
            simulation_path=args.simulation,
            metrics_path=args.metrics,
            sampling_path=args.sampling,
            evidence_manifest_path=args.evidence_manifest,
            formats=args.format,
            reports_dir=args.reports_dir,
        )
        print("Reports generated:")
        for path in outputs:
            print(f"- {path}")
        return 0

    if args.command == "run-report":
        result = run_from_basic_input(
            args.input,
            output_root=args.output_root,
            fetch_evidence=not args.no_fetch,
            purpose=args.purpose,
            variability_preset=args.variability_preset,
        )
        print(f"Run directory: {result['run_dir']}")
        print("Reports generated:")
        for path in result["reports"]:
            print(f"- {path}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
