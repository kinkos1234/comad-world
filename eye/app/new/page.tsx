"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { runPipeline, runPreflight, getSystemStatus, getLensCatalog, LensInfo, PreflightResult, ModelRecommendation, DeviceInfo } from "@/lib/api";

const CONFIG_META: Record<
  string,
  { desc: string; step: number; min: number; max: number }
> = {
  max_rounds: {
    desc: "시뮬레이션 반복 횟수",
    step: 1,
    min: 1,
    max: 50,
  },
  propagation_decay: {
    desc: "영향력 전파 시 감쇠 비율",
    step: 0.1,
    min: 0,
    max: 1,
  },
  max_hops: {
    desc: "영향력이 퍼지는 최대 단계",
    step: 1,
    min: 1,
    max: 10,
  },
  volatility_decay: {
    desc: "변동성이 줄어드는 속도",
    step: 0.01,
    min: 0,
    max: 1,
  },
  convergence_threshold: {
    desc: "수렴 판정 기준값 (작을수록 정밀)",
    step: 0.001,
    min: 0,
    max: 1,
  },
};

type ConfigType = {
  max_rounds: number;
  propagation_decay: number;
  max_hops: number;
  volatility_decay: number;
  convergence_threshold: number;
};

type PresetKey = "quick" | "balanced" | "precise" | "crisis";

const PRESETS: Record<
  PresetKey,
  {
    label: string;
    desc: string;
    values: ConfigType;
  }
> = {
  quick: {
    label: "빠른 탐색",
    desc: "대략적인 개요 파악",
    values: {
      max_rounds: 5,
      propagation_decay: 0.7,
      max_hops: 2,
      volatility_decay: 0.15,
      convergence_threshold: 0.05,
    },
  },
  balanced: {
    label: "균형",
    desc: "입력값에 대한 일반 시뮬레이션",
    values: {
      max_rounds: 10,
      propagation_decay: 0.6,
      max_hops: 3,
      volatility_decay: 0.1,
      convergence_threshold: 0.01,
    },
  },
  precise: {
    label: "정밀 분석",
    desc: "간접 효과 및 2차 파급까지 심층 분석",
    values: {
      max_rounds: 20,
      propagation_decay: 0.4,
      max_hops: 5,
      volatility_decay: 0.05,
      convergence_threshold: 0.005,
    },
  },
  crisis: {
    label: "고변동성",
    desc: "위기 상황의 변동성 분석",
    values: {
      max_rounds: 15,
      propagation_decay: 0.3,
      max_hops: 4,
      volatility_decay: 0.02,
      convergence_threshold: 0.005,
    },
  },
};

export default function NewAnalysis() {
  const router = useRouter();
  const [seedText, setSeedText] = useState("");
  const [analysisPrompt, setAnalysisPrompt] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [modelRecs, setModelRecs] = useState<ModelRecommendation[]>([]);
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [activePreset, setActivePreset] = useState<PresetKey | null>(
    "balanced",
  );
  const [config, setConfig] = useState<ConfigType>({
    ...PRESETS.balanced.values,
  });
  const [lenses, setLenses] = useState<LensInfo[]>([]);
  const [selectedLenses, setSelectedLenses] = useState<Set<string>>(new Set());
  const [showLenses, setShowLenses] = useState(false);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const preflightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    getSystemStatus()
      .then((s) => {
        setAvailableModels(s.available_models);
        if (s.llm_model) setSelectedModel(s.llm_model);
        if (s.model_recommendations) setModelRecs(s.model_recommendations);
        if (s.device) setDeviceInfo(s.device);
      })
      .catch(() => {});
    getLensCatalog()
      .then((catalog) => {
        setLenses(catalog.lenses);
        setSelectedLenses(new Set(catalog.default_ids));
      })
      .catch(() => {});
  }, []);

  // Debounced preflight
  useEffect(() => {
    if (preflightTimer.current) clearTimeout(preflightTimer.current);
    if (seedText.trim().length < 10) {
      setPreflight(null);
      return;
    }
    setPreflightLoading(true);
    preflightTimer.current = setTimeout(() => {
      runPreflight(seedText)
        .then((r) => setPreflight(r))
        .catch(() => setPreflight(null))
        .finally(() => setPreflightLoading(false));
    }, 800);
    return () => {
      if (preflightTimer.current) clearTimeout(preflightTimer.current);
    };
  }, [seedText]);

  const toggleLens = (id: string) => {
    setSelectedLenses((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const applyPreset = (key: PresetKey) => {
    setConfig({ ...PRESETS[key].values });
    setActivePreset(key);
  };

  const handleRun = async () => {
    if (!seedText.trim() || loading) return;
    setLoading(true);
    try {
      const { job_id } = await runPipeline({
        seed_text: seedText,
        analysis_prompt: analysisPrompt || undefined,
        model: selectedModel || undefined,
        ...config,
        lenses: selectedLenses.size > 0 ? Array.from(selectedLenses) : [],
      });
      router.push(`/run?job=${job_id}`);
    } catch (e) {
      alert(`실행 실패: ${e}`);
      setLoading(false);
    }
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setSeedText(text);
  };

  const adjustValue = (key: string, direction: 1 | -1) => {
    const meta = CONFIG_META[key];
    if (!meta) return;
    const current = config[key as keyof ConfigType];
    const next = Math.round((current + meta.step * direction) * 1000) / 1000;
    if (next >= meta.min && next <= meta.max) {
      setConfig({ ...config, [key]: next });
      setActivePreset(null); // 수동 조정 시 프리셋 해제
    }
  };

  return (
    <div className="p-10 space-y-8">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
        NEW ANALYSIS
      </h1>

      <div className="flex gap-6">
        {/* Seed Data */}
        <div className="flex-1 space-y-3">
          <p className="font-mono text-xs text-text-secondary">
            // seed_data
          </p>
          <textarea
            className="w-full h-[400px] bg-bg-card rounded-2xl p-6 font-mono text-sm text-text-primary resize-none focus:outline-none focus:ring-2 focus:ring-accent-orange/50 placeholder:text-bg-placeholder"
            placeholder="시드 데이터를 입력하거나 파일을 업로드하세요..."
            value={seedText}
            onChange={(e) => setSeedText(e.target.value)}
          />
          <label className="inline-flex items-center gap-2 px-4 py-2 bg-bg-elevated rounded-xl cursor-pointer hover:bg-bg-placeholder transition">
            <span className="font-mono text-xs text-text-secondary">
              upload_file
            </span>
            <input
              type="file"
              accept=".txt,.md,.csv"
              className="hidden"
              onChange={handleFile}
            />
          </label>

          {/* Preflight Info */}
          {(preflight || preflightLoading) && (
            <div className="mt-3 bg-bg-card rounded-2xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="font-mono text-[11px] text-text-secondary/80">
                  // preflight_diagnosis
                </p>
                {preflightLoading && (
                  <span className="inline-block w-2 h-4 bg-accent-teal animate-pulse" />
                )}
              </div>
              {preflight && (
                <>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span
                      className={`px-2.5 py-1 rounded-lg font-mono text-[11px] font-bold ${
                        preflight.risk_level === "low"
                          ? "bg-stance-positive/20 text-stance-positive"
                          : preflight.risk_level === "medium"
                          ? "bg-accent-orange/20 text-accent-orange"
                          : "bg-stance-negative/20 text-stance-negative"
                      }`}
                    >
                      {preflight.risk_level === "low"
                        ? "LOW RISK"
                        : preflight.risk_level === "medium"
                        ? "MEDIUM RISK"
                        : "HIGH RISK"}
                    </span>
                    <span className="font-mono text-[11px] text-text-secondary">
                      {preflight.chars.toLocaleString()} chars
                    </span>
                    <span className="font-mono text-[11px] text-accent-teal">
                      ~{preflight.estimated_tokens.toLocaleString()} tokens
                    </span>
                    <span className="font-mono text-[11px] text-text-secondary">
                      {preflight.sentences} sentences
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-mono text-[11px] text-text-secondary/80">
                      예상 배치: <span className="text-text-primary">{preflight.expected_batches}</span>
                    </span>
                    <span className="font-mono text-[11px] text-text-secondary/80">
                      예상 LLM 호출: <span className="text-text-primary">{preflight.expected_llm_calls}</span>
                    </span>
                  </div>
                  {preflight.warnings.length > 0 && (
                    <div className="space-y-1">
                      {preflight.warnings.map((w, i) => (
                        <p
                          key={i}
                          className="font-mono text-[11px] text-accent-orange"
                        >
                          ⚠ {w}
                        </p>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Analysis Prompt */}
          <div className="mt-4 space-y-2">
            <p className="font-mono text-xs text-text-secondary">
              // analysis_prompt (optional)
            </p>
            <textarea
              className="w-full h-[100px] bg-bg-card rounded-2xl p-4 font-mono text-sm text-text-primary resize-none focus:outline-none focus:ring-2 focus:ring-accent-teal/50 placeholder:text-bg-placeholder"
              placeholder="분석 주제나 관점을 입력하세요. 예: '삼성전자의 AI 반도체 경쟁력에서 TSMC 대비 약점과 기회 분석'"
              value={analysisPrompt}
              onChange={(e) => setAnalysisPrompt(e.target.value)}
            />
            <p className="font-mono text-[11px] text-text-secondary/80">
              입력 시 해당 주제에 초점을 맞춘 분석과 보고서가 생성됩니다
            </p>
          </div>

          {/* Lens Selection */}
          {lenses.length > 0 && (
            <div className="mt-4 space-y-2">
              <button
                type="button"
                onClick={() => setShowLenses(!showLenses)}
                className="flex items-center gap-2 font-mono text-xs text-text-secondary hover:text-text-primary transition"
              >
                <span className="text-accent-teal">{showLenses ? "▼" : "▶"}</span>
                // analysis_lenses ({selectedLenses.size > 0 ? `${selectedLenses.size}/${lenses.length}` : "auto"})
              </button>

              {showLenses && (
                <div className="bg-bg-card rounded-2xl p-5 space-y-3">
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-mono text-[11px] text-text-secondary/80">
                      분석공간에 적용할 지적 프레임워크 렌즈를 선택하세요
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedLenses(new Set(lenses.map(l => l.id)))}
                        className="font-mono text-[11px] text-accent-teal/80 hover:text-accent-teal transition"
                      >
                        전체 선택
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedLenses(new Set())}
                        className="font-mono text-[11px] text-text-secondary/60 hover:text-text-secondary transition"
                      >
                        전체 해제
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    {lenses.map((lens) => {
                      const active = selectedLenses.has(lens.id);
                      return (
                        <button
                          key={lens.id}
                          type="button"
                          onClick={() => toggleLens(lens.id)}
                          className={`relative px-3 py-2.5 rounded-xl text-left transition ${
                            active
                              ? "bg-accent-orange/10 ring-1 ring-accent-orange/30"
                              : "bg-bg-elevated hover:bg-bg-placeholder"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-4 h-4 rounded flex items-center justify-center text-[10px] font-bold ${
                                active
                                  ? "bg-accent-orange text-text-on-accent"
                                  : "bg-bg-placeholder text-text-secondary/40"
                              }`}
                            >
                              {active ? "✓" : ""}
                            </span>
                            <span
                              className={`font-mono text-xs font-medium ${
                                active ? "text-accent-orange" : "text-text-primary"
                              }`}
                            >
                              {lens.name_ko}
                            </span>
                            <span className="font-mono text-[11px] text-text-secondary/60">
                              {lens.name_en}
                            </span>
                          </div>
                          <p className="font-mono text-[11px] text-text-secondary/80 mt-1 pl-6 leading-tight">
                            {lens.framework}
                          </p>
                        </button>
                      );
                    })}
                  </div>

                  {selectedLenses.size > 0 ? (
                    <p className="font-mono text-[11px] text-accent-orange/80 mt-1">
                      {selectedLenses.size}개 렌즈 활성화 — 각 분석공간에 딥 필터로 적용됩니다
                    </p>
                  ) : (
                    <p className="font-mono text-[11px] text-accent-teal/80 mt-1">
                      미선택 시 LLM이 시드 데이터와 분석 주제에 맞는 렌즈를 자동 선별합니다
                      (분석 깊이에 따라 3~10개)
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Config Panel */}
        <div className="w-[320px] space-y-3">
          <p className="font-mono text-xs text-text-secondary">
            // simulation_config
          </p>
          <div className="bg-bg-card rounded-2xl p-6 space-y-5">
            {/* Model Selector */}
            <div className="space-y-1">
              <span className="font-mono text-xs text-text-secondary">
                llm_model
              </span>
              {availableModels.length > 0 ? (
                <>
                  <div className="space-y-1">
                    {availableModels.map((m) => {
                      const rec = modelRecs.find((r) => r.name === m);
                      const fitness = rec?.fitness || "unknown";
                      const isSelected = selectedModel === m;
                      return (
                        <button
                          key={m}
                          type="button"
                          onClick={() => setSelectedModel(m)}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg font-mono text-xs transition ${
                            isSelected
                              ? "bg-accent-teal/15 ring-1 ring-accent-teal/40 text-accent-teal"
                              : "bg-bg-elevated hover:bg-bg-placeholder text-text-primary"
                          }`}
                        >
                          <span className="truncate mr-2">{m}</span>
                          <span
                            className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              fitness === "safe"
                                ? "bg-stance-positive/20 text-stance-positive"
                                : fitness === "warning"
                                ? "bg-accent-orange/20 text-accent-orange"
                                : fitness === "danger"
                                ? "bg-stance-negative/20 text-stance-negative"
                                : "bg-bg-placeholder text-text-secondary/60"
                            }`}
                          >
                            {fitness === "safe"
                              ? "SAFE"
                              : fitness === "warning"
                              ? "WARN"
                              : fitness === "danger"
                              ? "DANGER"
                              : "—"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  {/* Selected model warning */}
                  {(() => {
                    const rec = modelRecs.find((r) => r.name === selectedModel);
                    if (!rec) return null;
                    if (rec.fitness === "danger")
                      return (
                        <div className="mt-1 p-2 rounded-lg bg-stance-negative/10 border border-stance-negative/20">
                          <p className="font-mono text-[11px] text-stance-negative font-bold">
                            RAM 초과 위험
                          </p>
                          <p className="font-mono text-[11px] text-stance-negative/80 mt-0.5">
                            {rec.reason}
                          </p>
                          {rec.parameter_size && (
                            <p className="font-mono text-[11px] text-text-secondary/60 mt-0.5">
                              모델: {rec.parameter_size} / 파일: {rec.size_gb.toFixed(1)}GB
                            </p>
                          )}
                        </div>
                      );
                    if (rec.fitness === "warning")
                      return (
                        <div className="mt-1 p-2 rounded-lg bg-accent-orange/10 border border-accent-orange/20">
                          <p className="font-mono text-[11px] text-accent-orange/80">
                            {rec.reason}
                          </p>
                        </div>
                      );
                    return null;
                  })()}
                </>
              ) : (
                <p className="font-mono text-[11px] text-text-secondary/80 py-2">
                  Ollama 연결 대기 중...
                </p>
              )}
              {deviceInfo && deviceInfo.total_ram_gb > 0 && (
                <p className="font-mono text-[11px] text-text-secondary/60">
                  {deviceInfo.os_name} {deviceInfo.arch} / RAM {deviceInfo.total_ram_gb}GB / {deviceInfo.gpu_type.toUpperCase()}
                </p>
              )}
            </div>

            <div className="border-t border-bg-placeholder/30" />

            {/* Presets */}
            <div className="space-y-2">
              <span className="font-mono text-xs text-text-secondary">
                preset
              </span>
              <div className="grid grid-cols-2 gap-2">
                {(Object.entries(PRESETS) as [PresetKey, (typeof PRESETS)[PresetKey]][]).map(
                  ([key, preset]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => applyPreset(key)}
                      className={`relative px-3 py-2.5 rounded-xl text-left transition group ${
                        activePreset === key
                          ? "bg-accent-teal/15 ring-1 ring-accent-teal/40"
                          : "bg-bg-elevated hover:bg-bg-placeholder"
                      }`}
                    >
                      <span
                        className={`font-mono text-xs font-medium ${
                          activePreset === key
                            ? "text-accent-teal"
                            : "text-text-primary"
                        }`}
                      >
                        {preset.label}
                      </span>
                      <p className="font-mono text-[11px] text-text-secondary/80 mt-0.5 leading-tight">
                        {preset.desc}
                      </p>
                    </button>
                  ),
                )}
              </div>
              {activePreset && (
                <p className="font-mono text-[11px] text-accent-teal/80">
                  {PRESETS[activePreset].label} 프리셋 적용됨 — 아래에서 개별
                  조정 가능
                </p>
              )}
            </div>

            <div className="border-t border-bg-placeholder/30" />

            {/* Parameter Controls */}
            {Object.entries(config).map(([key, value]) => {
              const meta = CONFIG_META[key];
              return (
                <div key={key} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-text-secondary">
                      {key}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => adjustValue(key, -1)}
                        className="w-6 h-6 flex items-center justify-center rounded-md bg-bg-elevated hover:bg-bg-placeholder text-text-secondary text-xs transition"
                      >
                        -
                      </button>
                      <input
                        type="number"
                        step={meta?.step ?? 0.1}
                        min={meta?.min}
                        max={meta?.max}
                        className="w-16 bg-bg-elevated rounded-lg px-2 py-1 font-mono text-xs text-accent-teal text-center focus:outline-none focus:ring-1 focus:ring-accent-teal/30"
                        value={value}
                        onChange={(e) => {
                          setConfig({
                            ...config,
                            [key]: parseFloat(e.target.value) || 0,
                          });
                          setActivePreset(null);
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => adjustValue(key, 1)}
                        className="w-6 h-6 flex items-center justify-center rounded-md bg-bg-elevated hover:bg-bg-placeholder text-text-secondary text-xs transition"
                      >
                        +
                      </button>
                    </div>
                  </div>
                  {meta && (
                    <p className="font-mono text-[11px] text-text-secondary/80 pl-0.5">
                      {meta.desc}
                    </p>
                  )}
                </div>
              );
            })}

            <button
              onClick={handleRun}
              disabled={!seedText.trim() || loading}
              className="w-full mt-4 py-3 bg-accent-orange text-text-on-accent rounded-2xl font-[family-name:var(--font-display)] text-sm font-bold tracking-wider disabled:opacity-40 hover:opacity-90 transition"
            >
              {loading ? "▶ RUNNING..." : "▶ RUN SIMULATION"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
