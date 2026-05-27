import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, User, Bot, ChevronLeft, RotateCcw, ChevronDown, Mic, Square } from 'lucide-react';
import { loadChatHistory, resetChatConversation, sendChatMessageStream, fetchSouls, Soul, transcribeVoice } from '../services/agentService';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const tryParseJson = (text: string) => {
  if (!text.startsWith('{')) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

const formatShanghaiTime = (value: string | undefined) => {
  if (!value) return value ?? '';
  if (/^\d{1,2}:\d{2}$/.test(value)) return value;
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Shanghai' });
};

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: Date;
}

interface AiChatPanelProps {
  onClose: () => void;
  isOpen: boolean;
  userId: string | null;
}

const AiChatPanel: React.FC<AiChatPanelProps> = ({ onClose, isOpen, userId }) => {
  const safeUserId = String(userId || '').trim();
  const quickPrompts = ['今晚如何更省电？', '现在应该充电还是放电？', 'EV 何时充电最划算？'];
  const buildWelcomeMessage = (targetUserId: string): Message => ({
    id: '1',
    sender: 'ai',
    text: `您好，我是 FeSolar 家庭助手。当前已绑定 ${targetUserId}，可以一起优化今天的用能策略。`,
    timestamp: new Date(),
  });
  const [messages, setMessages] = useState<Message[]>([buildWelcomeMessage(safeUserId)]);

  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [typingStatus, setTypingStatus] = useState('');
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [selectedSoul, setSelectedSoul] = useState('');
  const [souls, setSouls] = useState<Soul[]>([]);
  const [soulsLoaded, setSoulsLoaded] = useState(false);
  const [showSoulDropdown, setShowSoulDropdown] = useState(false);
  const [activeStreamMessageId, setActiveStreamMessageId] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!isOpen || !safeUserId) return;

    let cancelled = false;
    setIsLoadingHistory(true);
    setInputValue('');
    setIsTyping(false);
    setMessages([buildWelcomeMessage(safeUserId)]);

    loadChatHistory(safeUserId)
      .then((historyResult) => {
        if (cancelled) return;
        const loadedMessages = (historyResult.history || [])
          .map((item, index) => {
            const sender: Message['sender'] = item.role === 'user' ? 'user' : 'ai';
            const text = String(item.content || '').trim();
            if (!text) return null;
            return {
              id: `history-${index}-${sender}`,
              sender,
              text,
              timestamp: historyResult.updated_at ? new Date(historyResult.updated_at * 1000) : new Date(),
            };
          })
          .filter((item): item is Message => item !== null);

        setMessages(loadedMessages.length > 0 ? loadedMessages : [buildWelcomeMessage(safeUserId)]);
        setIsLoadingHistory(false);
      })
      .catch(() => {
        if (cancelled) return;
        setMessages([buildWelcomeMessage(safeUserId)]);
        setIsLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, safeUserId]);

  useEffect(() => {
    if (soulsLoaded) return;

    let cancelled = false;
    fetchSouls()
      .then(({ souls: loadedSouls, defaultSoul }) => {
        if (cancelled) return;
        setSouls(loadedSouls);
        setSelectedSoul((current) => {
          if (current && loadedSouls.some((soul) => soul.name === current)) return current;
          return defaultSoul || loadedSouls[0]?.name || '';
        });
        setSoulsLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setSoulsLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [soulsLoaded]);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const handleResetConversation = async () => {
    if (!safeUserId || isResetting) return;
    setIsResetting(true);
    setIsTyping(false);
    setTypingStatus('');
    setActiveStreamMessageId('');
    try {
      await resetChatConversation(safeUserId);
      setMessages([buildWelcomeMessage(safeUserId)]);
      setInputValue('');
    } finally {
      setIsResetting(false);
    }
  };

  const handleSend = async (textOverride?: string) => {
    const textToSend = textOverride || inputValue;
    if (!textToSend.trim() || isLoadingHistory || isResetting) return;
    if (!selectedSoul) {
      setTypingStatus(soulsLoaded ? '暂无可用 Soul' : '正在加载 Soul');
      setTimeout(() => setTypingStatus(''), 2000);
      return;
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: textToSend,
      timestamp: new Date(),
    };
    const streamAiMsgId = `${Date.now() + 1}-stream`;
    let sawDelta = false;
    let resultText = '';

    setMessages((prev) => [
      ...prev,
      userMsg,
      {
        id: streamAiMsgId,
        sender: 'ai',
        text: '',
        timestamp: new Date(),
      },
    ]);
    if (!textOverride) setInputValue('');
    setIsTyping(true);
    setTypingStatus('正在准备请求');
    setActiveStreamMessageId(streamAiMsgId);

    const aiResponseText = await sendChatMessageStream(
      textToSend,
      safeUserId,
      selectedSoul,
      (event) => {
        if (event.type === 'state' && event.message) {
          setTypingStatus(event.message);
          return;
        }
        if (event.type === 'lifecycle' && event.message) {
          setTypingStatus(event.message);
          return;
        }
        if (event.type === 'result') {
          resultText = String(event.response || '').trim();
          setTypingStatus('正在生成回答');
          if (resultText) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === streamAiMsgId
                  ? { ...msg, text: resultText }
                  : msg
              )
            );
          }
          return;
        }
        if (event.type === 'delta' && event.text) {
          sawDelta = true;
          setTypingStatus('正在生成回答');
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamAiMsgId
                ? { ...msg, text: `${msg.text}${event.text}` }
                : msg
            )
          );
        }
      },
    );

    setMessages((prev) => {
      const hasStreamMsg = prev.some((msg) => msg.id === streamAiMsgId);
      if (!hasStreamMsg) {
        return [
          ...prev,
          {
            id: (Date.now() + 2).toString(),
            sender: 'ai',
            text: aiResponseText,
            timestamp: new Date(),
          },
        ];
      }
      return prev.map((msg) => {
        if (msg.id !== streamAiMsgId) return msg;
        const fallbackText = String(resultText || aiResponseText || '').trim();
        if (!sawDelta) {
          return { ...msg, text: fallbackText };
        }
        if (fallbackText && msg.text !== fallbackText) {
          return { ...msg, text: fallbackText };
        }
        if (!msg.text.trim() && fallbackText) {
          return { ...msg, text: fallbackText };
        }
        return msg;
      });
    });
    setIsTyping(false);
    setTypingStatus('');
    setActiveStreamMessageId('');
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') handleSend();
  };

  const blobToDataURL = (blob: Blob): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Failed to read audio blob'));
      reader.readAsDataURL(blob);
    });

  const stopVoiceInput = () => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }
  };

  const startVoiceInput = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      audioChunksRef.current = [];

      const preferred = 'audio/webm;codecs=opus';
      const options = MediaRecorder.isTypeSupported(preferred) ? { mimeType: preferred } : undefined;
      const recorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        setIsRecording(false);
        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach((track) => track.stop());
          mediaStreamRef.current = null;
        }

        const chunks = audioChunksRef.current;
        audioChunksRef.current = [];
        if (!chunks.length) return;

        setIsTranscribing(true);
        try {
          const mimeType = recorder.mimeType || 'audio/webm';
          const blob = new Blob(chunks, { type: mimeType });
          const dataUrl = await blobToDataURL(blob);
          const recognizedText = await transcribeVoice(dataUrl, mimeType);
          if (recognizedText) {
            setInputValue((prev) => {
              const current = String(prev || '').trim();
              return current ? `${current} ${recognizedText}` : recognizedText;
            });
          }
        } catch (error) {
          console.error('Voice transcription failed:', error);
          setTypingStatus('语音识别失败，请重试');
          setTimeout(() => setTypingStatus(''), 2000);
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Failed to start voice recording:', error);
      setTypingStatus('无法访问麦克风');
      setTimeout(() => setTypingStatus(''), 2000);
      setIsRecording(false);
    }
  };

  const toggleVoiceInput = async () => {
    if (isTranscribing || isLoadingHistory || isResetting) return;
    if (isRecording) {
      stopVoiceInput();
      return;
    }
    await startVoiceInput();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[140] flex items-end justify-end bg-[rgba(68,85,109,0.28)] p-3 sm:p-6" onClick={onClose}>
      <div
        className="panel-enter glass-hero flex h-[min(88vh,780px)] w-full max-w-[450px] flex-col overflow-hidden rounded-[32px] border border-[#becde4]/72 shadow-[0_36px_78px_rgba(90,104,138,0.3)]"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="FeSolar 家庭助手对话框"
      >
        <div className="flex items-center justify-between border-b border-[#cbdbee]/72 bg-[linear-gradient(140deg,rgba(242,247,255,0.94),rgba(231,239,253,0.78))] px-5 py-4">
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="-ml-1 rounded-full p-2 text-[#7088a5] transition-colors hover:bg-[#edf4fb]"
              aria-label="返回"
            >
              <ChevronLeft size={20} />
            </button>
            <div>
              <h3 className="font-heading flex items-center gap-2 text-[15px] font-bold text-[#3f546e]">
                FeSolar 助手
                <Sparkles size={14} className="text-[#7a8fad]" />
              </h3>
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[#84b189] pulse-soft" />
                <span className="text-[10px] uppercase tracking-wider text-[#7d90a9]">鍦ㄧ嚎</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                onClick={() => setShowSoulDropdown(!showSoulDropdown)}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#bfcae9] bg-white/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#6677b6] transition-colors hover:bg-[#edf4fb]"
              >
                <span>{selectedSoul || (soulsLoaded ? 'Soul' : '加载中')}</span>
                <ChevronDown size={12} />
              </button>
              {showSoulDropdown && souls.length > 0 && (
                <div className="absolute right-0 top-full mt-2 w-48 rounded-xl border border-[#bfcae9] bg-white shadow-lg z-50">
                  {souls.map((soul) => (
                    <button
                      key={soul.name}
                      onClick={() => {
                        setSelectedSoul(soul.name);
                        setShowSoulDropdown(false);
                      }}
                      className={`w-full px-4 py-2 text-left text-[12px] transition-colors hover:bg-[#edf4fb] first:rounded-t-xl last:rounded-b-xl ${
                        selectedSoul === soul.name
                          ? 'bg-[#e8f1fd] font-semibold text-[#3f546e]'
                          : 'text-[#6677b6]'
                      }`}
                    >
                      <div className="font-semibold capitalize">{soul.name}</div>
                      {soul.description && (
                        <div className="text-[10px] text-[#888aaa]">{soul.description}</div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={handleResetConversation}
              disabled={isResetting}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#bfcae9] bg-white/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#6677b6] transition-colors hover:bg-[#edf4fb] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RotateCcw size={12} />
              {isResetting ? '重置中' : '重置对话'}
            </button>
            <span className="rounded-full border border-[#bfcae9] bg-white/56 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.13em] text-[#6677b6]">
              Home Copilot
            </span>
          </div>
        </div>

        <div className="scrollbar-hide flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-[linear-gradient(180deg,rgba(249,252,255,0.9),rgba(236,244,252,0.44))] p-4">
          {isLoadingHistory ? (
            <div className="rounded-2xl border border-[#c5d6ec] bg-[linear-gradient(145deg,#f8fbff,#edf4fc)] px-4 py-3 text-sm text-[#5f7695] shadow-sm">
              正在加载历史对话...
            </div>
          ) : null}
          {messages.map((msg) => {
            let parsedContent = null;
            if (msg.sender === 'ai') {
              parsedContent = tryParseJson(msg.text);
            }
            return (
              <div key={msg.id} className={`flex items-end gap-2 ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div
                  className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border ${msg.sender === 'ai'
                    ? 'border-[#c8d9ec] bg-[#eef5fc] text-[#6f8cae]'
                    : 'border-[#c3d4e8] bg-[#e7f1fb] text-[#6a86a8]'
                    }`}
                >
                  {msg.sender === 'ai' ? <Bot size={16} /> : <User size={16} />}
                </div>

                <div className="flex flex-col gap-2 max-w-[84%]">
                  <div
                    className={`rounded-2xl p-3 text-sm leading-relaxed shadow-sm whitespace-pre-wrap ${msg.sender === 'user'
                      ? 'rounded-br-none border border-[#bccde4] bg-[linear-gradient(145deg,#eaf3fd,#deebf8)] text-[#577191]'
                      : 'rounded-bl-none border border-[#c5d6ec] bg-[linear-gradient(145deg,#f8fbff,#edf4fc)] text-[#5f7695]'
                      }`}
                  >
                    {msg.sender === 'ai' && msg.id === activeStreamMessageId && !msg.text.trim() ? (
                      <div className="flex gap-1">
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#778faa]" style={{ animationDelay: '0ms' }} />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#778faa]" style={{ animationDelay: '150ms' }} />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#778faa]" style={{ animationDelay: '300ms' }} />
                      </div>
                    ) : parsedContent && parsedContent.ui_widget === 'LINE_CHART' ? (
                      <div className="flex flex-col gap-3 w-full min-w-[280px] sm:min-w-[320px]">
                        <div>{parsedContent.text}</div>
                        <div className="h-56 w-full bg-white/60 rounded-xl p-2 border border-[#bccde4]">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart
                              data={parsedContent.chart_data?.map((row: any) => ({
                                ...row,
                                time: formatShanghaiTime(row.time ?? row.timestamp),
                              }))}
                              margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eaf0f6" />
                              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#8f9fb3' }} axisLine={false} tickLine={false} minTickGap={20} />
                              <YAxis
                                tick={{ fontSize: 10, fill: '#8f9fb3' }}
                                axisLine={false}
                                tickLine={false}
                                width={45}
                                tickFormatter={(value) => `${value}W`}
                              />
                              <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                              <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '11px', paddingTop: '4px' }} />
                              <Line type="monotone" dataKey="pv" name="光伏功率" stroke="#f59e0b" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                              <Line type="monotone" dataKey="load" name="家庭负载" stroke="#3b82f6" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    ) : (
                      msg.text
                    )}
                  </div>
                  {msg.sender === 'ai' && msg.id === activeStreamMessageId && isTyping && typingStatus ? (
                    <div className="px-1 text-xs text-[#6f85a3]">
                      {typingStatus}
                    </div>
                  ) : null}
                  {parsedContent?.actions && (
                    <div className="flex flex-wrap gap-2 mt-1">
                      {parsedContent.actions.map((action: any, idx: number) => (
                        <button
                          key={idx}
                          onClick={() => handleSend(action.command)}
                          className="rounded-full border border-[#cbdbee] bg-white/80 px-3 py-1.5 text-xs font-medium text-[#5f7695] transition-all hover:bg-[#e6effb] hover:border-[#b8c9e0] active:scale-95 shadow-sm"
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {isTyping && !activeStreamMessageId ? (
            <div className="flex items-end gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[#c8d9ec] bg-[#eef5fc] text-[#6f8cae]">
                <Bot size={16} />
              </div>
              <div className="rounded-2xl rounded-bl-none border border-[#c8d9ec] bg-[#f5f9fe] px-4 py-3">
                <div className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#778faa]" style={{ animationDelay: '0ms' }} />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#778faa]" style={{ animationDelay: '150ms' }} />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#778faa]" style={{ animationDelay: '300ms' }} />
                </div>
                {typingStatus ? (
                  <div className="mt-2 text-xs text-[#6f85a3]">{typingStatus}</div>
                ) : null}
              </div>
            </div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-[#cbdbee]/72 bg-[rgba(248,252,255,0.92)] p-4">
          <div className="mb-3 flex flex-wrap gap-2">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => setInputValue(prompt)}
                className="rounded-full border border-[#c3d2ea] bg-white/72 px-3 py-1.5 text-[11px] font-medium text-[#657da0] transition-colors hover:bg-[#edf4fc]"
              >
                {prompt}
              </button>
            ))}
          </div>
          <div className="relative">
            <input
              type="text"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="询问家庭用能建议..."
              className="w-full rounded-2xl border border-[#c5d6ea] bg-white/90 py-3.5 pl-12 pr-12 text-sm text-[#5a738f] outline-none transition-colors focus:border-[#7693b6]"
            />
            <button
              onClick={toggleVoiceInput}
              disabled={isLoadingHistory || isResetting || isTranscribing}
              className={`absolute left-2 top-1/2 -translate-y-1/2 rounded-xl p-2 text-white shadow-sm transition-all duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] disabled:cursor-not-allowed disabled:opacity-50 ${
                isRecording ? 'bg-[#c55b5b] hover:bg-[#b44e4e]' : 'bg-[#6f8fb4] hover:bg-[#6484a8]'
              }`}
              aria-label={isRecording ? '停止录音' : '开始录音'}
              title={isTranscribing ? '语音识别中...' : isRecording ? '点击停止录音' : '点击开始录音'}
            >
              {isRecording ? <Square size={16} /> : <Mic size={16} />}
            </button>
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoadingHistory || isResetting}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl bg-[#6f8fb4] p-2 text-white shadow-sm transition-all duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:bg-[#6484a8] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AiChatPanel;

