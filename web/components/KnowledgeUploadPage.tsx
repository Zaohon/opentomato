import React, { useMemo, useRef, useState } from 'react';
import { ArrowLeft, CheckCircle2, FileText, UploadCloud, XCircle } from 'lucide-react';

import { uploadResourceFile } from '../services/agentService';

type UploadStatus = 'pending' | 'uploading' | 'success' | 'failed';

type UploadItem = {
  id: string;
  file: File;
  status: UploadStatus;
  message: string;
};

type KnowledgeUploadPageProps = {
  onBack: () => void;
};

const formatBytes = (bytes: number) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
};

const formatDateTime = (timestamp: number) => {
  if (!Number.isFinite(timestamp)) return '-';
  const d = new Date(timestamp);
  if (Number.isNaN(d.getTime())) return '-';
  return d.toLocaleString('zh-CN', { hour12: false });
};

const buildFileId = (file: File) => `${file.name}_${file.size}_${file.lastModified}`;

const allowedExtensions = ['pdf', 'doc', 'docx', 'txt', 'md', 'ppt', 'pptx', 'xls', 'xlsx'];

const KnowledgeUploadPage: React.FC<KnowledgeUploadPageProps> = ({ onBack }) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [uploader, setUploader] = useState('web-ui');
  const [dragging, setDragging] = useState(false);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [globalMessage, setGlobalMessage] = useState('');

  const canUpload = useMemo(() => items.some((item) => item.status === 'pending' || item.status === 'failed'), [items]);

  const mergeFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;

    const nextFiles = Array.from(fileList);
    setItems((prev) => {
      const seen = new Set(prev.map((item) => item.id));
      const appended: UploadItem[] = [];
      for (const file of nextFiles) {
        const id = buildFileId(file);
        if (seen.has(id)) continue;
        seen.add(id);
        appended.push({ id, file, status: 'pending', message: '' });
      }
      return [...prev, ...appended];
    });
    setGlobalMessage('');
  };

  const handleDrop: React.DragEventHandler<HTMLDivElement> = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setDragging(false);
    mergeFiles(event.dataTransfer.files);
  };

  const handleUpload = async () => {
    const candidates = items.filter((item) => item.status === 'pending' || item.status === 'failed');
    if (!candidates.length) {
      setGlobalMessage('没有可上传文件。');
      return;
    }

    setIsUploading(true);
    setGlobalMessage('');
    for (const item of candidates) {
      setItems((prev) =>
        prev.map((current) =>
          current.id === item.id ? { ...current, status: 'uploading', message: '上传中...' } : current
        )
      );

      try {
        const response = await uploadResourceFile({
          file: item.file,
          uploader: uploader.trim() || 'web-ui',
        });
        setItems((prev) =>
          prev.map((current) =>
            current.id === item.id
              ? {
                  ...current,
                  status: 'success',
                  message: response?.ingest_id ? `成功，ingest_id=${response.ingest_id}` : '成功',
                }
              : current
          )
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : '上传失败';
        setItems((prev) =>
          prev.map((current) =>
            current.id === item.id ? { ...current, status: 'failed', message } : current
          )
        );
      }
    }
    setIsUploading(false);
  };

  const summary = useMemo(() => {
    const success = items.filter((item) => item.status === 'success').length;
    const failed = items.filter((item) => item.status === 'failed').length;
    const total = items.length;
    return { success, failed, total };
  }, [items]);

  return (
    <div className="relative min-h-screen overflow-hidden px-5 py-5 text-[color:var(--ink-strong)] selection:bg-[#dbe8f6] md:px-8 md:py-6">
      <div className="pointer-events-none absolute -left-10 top-6 h-[24rem] w-[24rem] rounded-full bg-[#fff6e8]/76 blur-3xl" />
      <div className="pointer-events-none absolute right-0 top-0 h-[26rem] w-[26rem] rounded-full bg-[#d7e6f9]/62 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-[#e0edf9]/56 blur-3xl" />

      <div className="relative mx-auto flex w-full max-w-[1260px] flex-col gap-5">
        <header className="glass-hero rounded-[36px] px-5 py-5 md:px-8 md:py-6">
          <div className="mb-3 flex items-center gap-2">
            <button
              onClick={onBack}
              type="button"
              className="glass-chip inline-flex items-center gap-1 rounded-full border border-[#c3d3e8]/78 bg-white/60 px-3 py-1.5 text-xs font-semibold text-[#6d84a2] transition-colors hover:bg-white/75"
            >
              <ArrowLeft size={13} />
              返回
            </button>
            <span className="glass-chip inline-flex items-center gap-1 rounded-full border border-[#bfd0e6]/70 bg-white/55 px-3 py-1.5 text-xs font-semibold text-[#627997]">
              Knowledge Upload
            </span>
          </div>
          <h1 className="font-heading text-3xl font-bold leading-tight text-[#324358] md:text-4xl">资源知识库上传</h1>
          <p className="mt-3 text-sm text-[#6f8096]">拖拽或选择文件后，前端会展示基础信息；确认上传后调用 Agent 的 `/resources/upload` 接口。</p>
        </header>

        <section className="glass-card rounded-[30px] p-4 md:p-6">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setDragging(true);
            }}
            onDragEnter={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setDragging(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setDragging(false);
            }}
            onDrop={handleDrop}
            className="rounded-3xl border-2 border-dashed p-7 text-center transition-colors"
            style={{
              borderColor: dragging ? 'rgba(110,145,184,0.92)' : 'rgba(169,188,212,0.78)',
              background: dragging
                ? 'linear-gradient(145deg, rgba(238,245,255,0.92), rgba(227,238,252,0.62))'
                : 'linear-gradient(145deg, rgba(252,254,255,0.82), rgba(240,247,253,0.5))',
            }}
          >
            <UploadCloud className="mx-auto mb-3 text-[#5f7ea2]" size={34} />
            <div className="text-sm font-semibold text-[#42566f]">拖拽文件到这里，或点击选择文件</div>
            <div className="mt-1 text-xs text-[#72859e]">支持：{allowedExtensions.join(', ')}</div>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-4 rounded-full border border-[#b8cbdf] bg-white/70 px-4 py-2 text-sm font-semibold text-[#5b789d] transition-colors hover:bg-white"
            >
              选择文件
            </button>
            <input
              ref={inputRef}
              type="file"
              multiple
              className="hidden"
              accept={allowedExtensions.map((ext) => `.${ext}`).join(',')}
              onChange={(event) => {
                mergeFiles(event.target.files);
                event.currentTarget.value = '';
              }}
            />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="text-xs font-semibold text-[#6b809d]">
              目标资源 URI
              <input
                disabled
                className="mt-1 w-full rounded-xl border border-[#bfd0e6]/75 bg-slate-100/70 px-3 py-2 text-sm text-[#7a8ea9] outline-none ring-0"
                placeholder="Managed by backend"
              />
            </label>
            <label className="text-xs font-semibold text-[#6b809d]">
              上传者标识
              <input
                value={uploader}
                onChange={(event) => setUploader(event.target.value)}
                className="mt-1 w-full rounded-xl border border-[#bfd0e6]/75 bg-white/70 px-3 py-2 text-sm text-[#3d5169] outline-none ring-0 focus:border-[#7d9bbe]"
                placeholder="web-ui"
              />
            </label>
          </div>

          <div className="mt-4 overflow-hidden rounded-2xl border border-[#bfd0e4]/66 bg-white/56">
            <div className="grid grid-cols-[minmax(0,2.2fr)_110px_130px_minmax(0,1.4fr)] gap-3 border-b border-[#c7d7e8]/72 px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-[#6b809d]">
              <span>文件</span>
              <span>大小</span>
              <span>状态</span>
              <span>说明</span>
            </div>
            <div className="max-h-[360px] overflow-auto">
              {items.length === 0 ? (
                <div className="px-4 py-6 text-sm text-[#7387a2]">还没有选择文件。</div>
              ) : (
                items.map((item) => {
                  const ext = item.file.name.split('.').pop()?.toLowerCase() || '-';
                  const iconColor =
                    item.status === 'success'
                      ? '#4d9a7f'
                      : item.status === 'failed'
                        ? '#c06f5f'
                        : item.status === 'uploading'
                          ? '#738cb6'
                          : '#6f8198';
                  return (
                    <div
                      key={item.id}
                      className="grid grid-cols-[minmax(0,2.2fr)_110px_130px_minmax(0,1.4fr)] gap-3 border-b border-[#d4e1ef]/58 px-4 py-3 text-sm text-[#41566f]"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 truncate font-semibold text-[#3f536b]">
                          <FileText size={15} style={{ color: iconColor }} />
                          <span className="truncate">{item.file.name}</span>
                        </div>
                        <div className="mt-1 text-xs text-[#7c90a8]">扩展名: {ext} · 修改时间: {formatDateTime(item.file.lastModified)}</div>
                      </div>
                      <div className="text-xs text-[#617a97]">{formatBytes(item.file.size)}</div>
                      <div className="text-xs font-semibold">
                        {item.status === 'success' ? (
                          <span className="inline-flex items-center gap-1 text-[#4d9a7f]">
                            <CheckCircle2 size={14} />
                            成功
                          </span>
                        ) : item.status === 'failed' ? (
                          <span className="inline-flex items-center gap-1 text-[#bf6b5e]">
                            <XCircle size={14} />
                            失败
                          </span>
                        ) : item.status === 'uploading' ? (
                          <span className="text-[#6b84ad]">上传中</span>
                        ) : (
                          <span className="text-[#7389a4]">待上传</span>
                        )}
                      </div>
                      <div className="break-words text-xs text-[#697f99]">{item.message || '-'}</div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-[#6f839e]">
              已选择 {summary.total} 个文件，成功 {summary.success}，失败 {summary.failed}
            </div>
            <button
              type="button"
              disabled={!canUpload || isUploading}
              onClick={handleUpload}
              className="rounded-xl border border-[#b5c8df] bg-[linear-gradient(145deg,rgba(247,252,255,0.86),rgba(225,238,252,0.64))] px-4 py-2 text-sm font-semibold text-[#4e6f95] transition-opacity disabled:cursor-not-allowed disabled:opacity-55"
            >
              {isUploading ? '上传中...' : '确认上传'}
            </button>
          </div>

          {globalMessage ? (
            <div className="mt-3 rounded-xl border border-[#dfc7ba] bg-[#fff6ef]/82 px-3 py-2 text-xs text-[#a37158]">
              {globalMessage}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
};

export default KnowledgeUploadPage;
