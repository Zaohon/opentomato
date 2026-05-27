import React, { useEffect, useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { Download, FileUp, Play, Square } from "lucide-react";
import { fetchSouls, sendChatMessageStream, Soul } from "../services/agentService";

type BatchTestStatus = "pending" | "running" | "success" | "failed";

type BatchTestRow = {
  index: number;
  userId: string;
  question: string;
  answer: string;
  status: BatchTestStatus;
  elapsedMs: number;
  error?: string;
};

const SAMPLE_FILENAME = "batch_question_sample.xlsx";
const REPORT_FILENAME_PREFIX = "batch_test_report";
const CONCURRENT_USERS = 10;
const DEFAULT_BATCH_TEST_SOUL = "果断";
const FALLBACK_SOULS: Soul[] = [
  { name: "果断", description: "直接、高效、行动导向" },
  { name: "热情", description: "积极、鼓励、表达充分" },
  { name: "守护", description: "稳妥、谨慎、重视安全" },
  { name: "共情", description: "温和、理解、关注感受" },
];
const TEST_USERS = Array.from({ length: CONCURRENT_USERS }, (_, index) => String(index + 1).padStart(3, "0"));

const parseQuestionsFromWorkbook = (arrayBuffer: ArrayBuffer): string[] => {
  const workbook = XLSX.read(arrayBuffer, { type: "array" });
  const firstSheetName = workbook.SheetNames[0];
  if (!firstSheetName) return [];
  const sheet = workbook.Sheets[firstSheetName];
  const rows = XLSX.utils.sheet_to_json<(string | number | null)[]>(sheet, {
    header: 1,
    defval: "",
    blankrows: false,
  });
  if (!rows.length) return [];

  const firstCell = String(rows[0]?.[0] ?? "").trim().toLowerCase();
  const startAt = firstCell === "question" || firstCell === "问题" ? 1 : 0;

  const questions: string[] = [];
  for (let i = startAt; i < rows.length; i += 1) {
    const value = String(rows[i]?.[0] ?? "").trim();
    if (!value) continue;
    questions.push(value);
  }
  return questions;
};

const downloadWorkbook = (filename: string, data: (string | number)[][], sheetName: string) => {
  const worksheet = XLSX.utils.aoa_to_sheet(data);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
  XLSX.writeFile(workbook, filename);
};

const BatchQuestionTestPanel: React.FC = () => {
  const [questions, setQuestions] = useState<string[]>([]);
  const [rows, setRows] = useState<BatchTestRow[]>([]);
  const [running, setRunning] = useState(false);
  const [processed, setProcessed] = useState(0);
  const [errorText, setErrorText] = useState("");
  const [souls, setSouls] = useState<Soul[]>(FALLBACK_SOULS);
  const [selectedSoul, setSelectedSoul] = useState(DEFAULT_BATCH_TEST_SOUL);
  const stopRequestedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const loadSouls = async () => {
      try {
        const loadedSouls = await fetchSouls();
        if (!cancelled && loadedSouls.length > 0) {
          setSouls(loadedSouls);
          if (!loadedSouls.some((soul) => soul.name === DEFAULT_BATCH_TEST_SOUL)) {
            setSelectedSoul(loadedSouls[0].name);
          }
        }
      } catch {
        if (!cancelled) {
          setSouls(FALLBACK_SOULS);
        }
      }
    };
    void loadSouls();
    return () => {
      cancelled = true;
    };
  }, []);

  const progress = useMemo(() => {
    if (!questions.length) return 0;
    return Math.min(100, Math.round((processed / questions.length) * 100));
  }, [processed, questions.length]);

  const onDownloadSample = () => {
    downloadWorkbook(
      SAMPLE_FILENAME,
      [
        ["question"],
        ["你是谁"],
        ["我是谁"],
        ["请给我一条今天的用能建议"],
      ],
      "questions"
    );
  };

  const onUploadFile = async (file: File) => {
    setErrorText("");
    try {
      const arrayBuffer = await file.arrayBuffer();
      const parsed = parseQuestionsFromWorkbook(arrayBuffer);
      const initialRows = parsed.map((question, index) => ({
        index: index + 1,
        userId: TEST_USERS[index % TEST_USERS.length],
        question,
        answer: "",
        status: "pending" as BatchTestStatus,
        elapsedMs: 0,
        error: "",
      }));

      setQuestions(parsed);
      setRows(initialRows);
      setProcessed(0);
      if (!parsed.length) {
        setErrorText("Excel 中未读取到问题，请确保第一列包含问题文本。");
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "解析 Excel 失败");
    }
  };

  const runSingle = async (rowIndex: number, soul: string) => {
    const targetRow = rows[rowIndex];
    if (!targetRow) return;

    setRows((prev) =>
      prev.map((item) => (item.index === targetRow.index ? { ...item, status: "running", error: "" } : item))
    );

    const start = Date.now();
    try {
      const answer = await sendChatMessageStream(targetRow.question, targetRow.userId, soul);
      const elapsedMs = Date.now() - start;
      setRows((prev) =>
        prev.map((item) =>
          item.index === targetRow.index
            ? { ...item, answer: answer || "", status: "success", elapsedMs, error: "" }
            : item
        )
      );
    } catch (error) {
      const elapsedMs = Date.now() - start;
      const message = error instanceof Error ? error.message : "调用失败";
      setRows((prev) =>
        prev.map((item) =>
          item.index === targetRow.index
            ? { ...item, answer: "", status: "failed", elapsedMs, error: message }
            : item
        )
      );
    } finally {
      setProcessed((prev) => prev + 1);
    }
  };

  const onRun = async () => {
    if (running || !rows.length) return;
    const soulForRun = selectedSoul;
    setRunning(true);
    setErrorText("");
    setProcessed(0);
    stopRequestedRef.current = false;
    setRows((prev) =>
      prev.map((item) => ({
        ...item,
        answer: "",
        status: "pending",
        elapsedMs: 0,
        error: "",
      }))
    );

    const queue = Array.from({ length: rows.length }, (_, index) => index);
    const workerCount = Math.min(CONCURRENT_USERS, queue.length);

    const worker = async () => {
      while (queue.length > 0) {
        if (stopRequestedRef.current) return;
        const next = queue.shift();
        if (next === undefined) return;
        await runSingle(next, soulForRun);
      }
    };

    await Promise.all(Array.from({ length: workerCount }, () => worker()));
    setRunning(false);
  };

  const onStop = () => {
    if (!running) return;
    stopRequestedRef.current = true;
  };

  const onDownloadReport = () => {
    if (!rows.length) return;
    const now = new Date();
    const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(
      now.getDate()
    ).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(
      2,
      "0"
    )}${String(now.getSeconds()).padStart(2, "0")}`;
    const filename = `${REPORT_FILENAME_PREFIX}_${stamp}.xlsx`;

    const data: (string | number)[][] = [
      ["index", "user_id", "soul", "question", "status", "elapsed_ms", "answer", "error"],
      ...rows.map((row) => [
        row.index,
        row.userId,
        selectedSoul,
        row.question,
        row.status,
        row.elapsedMs,
        row.answer,
        row.error ?? "",
      ]),
    ];
    downloadWorkbook(filename, data, "report");
  };

  return (
    <section className="rounded-2xl bg-white p-7 shadow-sm xl:p-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">批量问题集测试</h2>
          <p className="mt-1 text-sm text-slate-600">
            上传 Excel 后并发测试。每题会分配到 10 个测试用户之一（001-010），并统一使用所选性格。
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs font-semibold text-slate-500">
            统一性格
            <select
              value={selectedSoul}
              onChange={(event) => setSelectedSoul(event.target.value)}
              disabled={running}
              className="min-w-[140px] rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              {souls.map((soul) => (
                <option key={soul.name} value={soul.name}>
                  {soul.name}
                </option>
              ))}
            </select>
          </label>
          <div className="pb-2 text-xs text-slate-500">并发用户数：{CONCURRENT_USERS}</div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onDownloadSample}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          <Download size={15} />
          下载示例问题集
        </button>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
          <FileUp size={15} />
          上传问题集
          <input
            type="file"
            className="hidden"
            accept=".xlsx,.xls"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              void onUploadFile(file);
              event.currentTarget.value = "";
            }}
          />
        </label>
        <button
          type="button"
          onClick={onRun}
          disabled={!rows.length || running}
          className="inline-flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-semibold text-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play size={15} />
          开始测试
        </button>
        <button
          type="button"
          onClick={onStop}
          disabled={!running}
          className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Square size={14} />
          停止派发
        </button>
        <button
          type="button"
          onClick={onDownloadReport}
          disabled={!rows.length || processed === 0}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Download size={15} />
          下载测试报告
        </button>
      </div>

      <div className="mb-3">
        <div className="mb-1 flex items-center justify-between text-sm text-slate-600">
          <span>
            进度：{processed}/{questions.length || 0}
          </span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
          <div className="h-full rounded-full bg-slate-500 transition-all duration-200" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {errorText ? <div className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{errorText}</div> : null}

      <div className="h-[560px] overflow-auto rounded-xl border border-slate-200">
        <table className="min-w-[1360px] w-full table-fixed text-left text-sm">
          <colgroup>
            <col style={{ width: "72px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "140px" }} />
            <col style={{ width: "120px" }} />
            <col style={{ width: "120px" }} />
            <col style={{ width: "auto" }} />
          </colgroup>
          <thead className="sticky top-0 bg-slate-50 text-slate-700">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">用户</th>
              <th className="px-3 py-2">问题</th>
              <th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">耗时(ms)</th>
              <th className="px-3 py-2">回答</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.index} className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 text-slate-500">{row.index}</td>
                <td className="px-3 py-2 text-slate-700">{row.userId}</td>
                <td className="px-3 py-2 whitespace-pre-wrap break-words text-slate-700">{row.question}</td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                      row.status === "success"
                        ? "bg-emerald-50 text-emerald-700"
                        : row.status === "failed"
                          ? "bg-rose-50 text-rose-700"
                          : row.status === "running"
                            ? "bg-amber-50 text-amber-700"
                            : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {row.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-slate-500">{row.elapsedMs || "-"}</td>
                <td className="px-3 py-2 whitespace-pre-wrap break-words text-slate-700">{row.answer || row.error || "-"}</td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td className="px-3 py-6 text-center text-slate-500" colSpan={6}>
                  请先上传问题集 Excel（第一列为问题，首行可用 question/问题 作为表头）
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default BatchQuestionTestPanel;
