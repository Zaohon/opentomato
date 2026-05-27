import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  Bell,
  Bot,
  ChevronRight,
  CloudSun,
  Coins,
  Leaf,
  LineChart,
  LogOut,
  MessageSquare,
  Shield,
  Sparkles,
  ThermometerSun,
  User,
  Wind,
  X,
  XCircle,
} from 'lucide-react';
import IsoHouse from './components/IsoHouse';
import SettingsPanel from './components/SettingsPanel';
import AiChatPanel from './components/AiChatPanel';
import KnowledgeUploadPage from './components/KnowledgeUploadPage';
import BatchQuestionTestPanel from './components/BatchQuestionTestPanel';
import { SystemMode, ComponentType, EnergyData, ChartDataPoint, PVForecastData } from './types';
import { generateSuggestion, getFeSolarAdvice } from './services/agentService';

const CHART_WIDTH = 720;
const CHART_HEIGHT = 250;
const CHART_PADDING = 20;
const HISTORY_CHART_WIDTH = 860;
const HISTORY_CHART_HEIGHT = 300;
const HISTORY_CHART_PADDING = 24;
const USER_ROUTE_PREFIX = '/user/';
const RESOURCE_UPLOAD_PATH = '/resources/upload';
const WEB_STUDIO_PATH = '/web-studio';
const TEST_USER_IDS = Array.from({ length: 20 }, (_, index) => String(index + 1));

type HistoryMetric = 'solar' | 'load' | 'battery' | 'ev';
type HistoryRange = 'day' | 'week' | 'month';
type HealthPayload = {
  ready?: boolean;
  strict?: boolean;
  timestamp?: string;
  concurrency?: {
    enabled?: boolean;
    global_max_concurrency?: number;
    per_lane_queue_cap?: number;
    queued_users?: number;
    queued_requests?: number;
    running_requests?: number;
    active_lanes?: number;
    running_lanes?: number;
  };
  [key: string]: unknown;
};

const isValidTestUserId = (userId: string) => TEST_USER_IDS.includes(userId);

const parseUserIdFromPath = (pathname: string): string | null => {
  const normalized = pathname.trim();
  if (!normalized.startsWith(USER_ROUTE_PREFIX)) {
    return null;
  }
  const userId = decodeURIComponent(normalized.slice(USER_ROUTE_PREFIX.length)).replace(/\/+$/, '');
  return userId || null;
};

const generatePowerData = (): ChartDataPoint[] => {
  const currentHour = 14;

  return Array.from({ length: 24 }, (_, i) => {
    const hour = i;
    const isDaytime = hour >= 6 && hour <= 19;
    const solarBase = isDaytime ? Math.sin(((hour - 6) / 13) * Math.PI) * 5 : 0;

    let solarActual: number | null = null;
    if (hour <= currentHour) {
      solarActual = Math.max(0, solarBase + (Math.random() * 0.8 - 0.2));
    }

    let solarPredicted: number | null = null;
    if (hour >= currentHour) {
      solarPredicted = Math.max(0, solarBase);
    }

    let consumption = 1.5 + Math.random();
    if ((hour >= 7 && hour <= 9) || (hour >= 18 && hour <= 21)) {
      consumption += 2.5;
    }

    const net = consumption - (solarActual || 0);

    const batteryProfile = [
      40, 38, 36, 35, 35, 35,
      40, 50, 65, 80, 95, 100, 100, 98, 95, 85, 75,
      70, 65, 60, 55, 50, 45, 42,
    ];

    return {
      time: `${hour}:00`,
      solar: solarActual ? +solarActual.toFixed(2) : null,
      solarPredicted: solarPredicted ? +solarPredicted.toFixed(2) : null,
      consumption: +consumption.toFixed(2),
      battery: batteryProfile[i] || 50,
      grid: +net.toFixed(2),
    };
  });
};

const formatTime = (iso: string) => {
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return '--:--';
  return dt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Shanghai' });
};

const buildLinePath = (values: number[], width: number, height: number, padding: number) => {
  if (!values.length) return '';

  const min = Math.min(...values);
  const max = Math.max(...values);
  const valueRange = Math.max(max - min, 0.01);
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;

  return values
    .map((value, index) => {
      const x = padding + (index / Math.max(values.length - 1, 1)) * innerWidth;
      const y = padding + (1 - (value - min) / valueRange) * innerHeight;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
};

const buildAreaPath = (values: number[], width: number, height: number, padding: number) => {
  if (!values.length) return '';

  const min = Math.min(...values);
  const max = Math.max(...values);
  const valueRange = Math.max(max - min, 0.01);
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;
  const bottom = height - padding;

  const points = values.map((value, index) => {
    const x = padding + (index / Math.max(values.length - 1, 1)) * innerWidth;
    const y = padding + (1 - (value - min) / valueRange) * innerHeight;
    return { x, y };
  });

  const line = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');

  const first = points[0];
  const last = points[points.length - 1];
  return `${line} L ${last.x.toFixed(2)} ${bottom.toFixed(2)} L ${first.x.toFixed(2)} ${bottom.toFixed(2)} Z`;
};

const modeTokens: Record<SystemMode, { title: string; desc: string; icon: React.ElementType; accent: string; ring: string }> = {
  [SystemMode.ECONOMIC]: {
    title: '经济模式',
    desc: '优先降低家庭电费',
    icon: Coins,
    accent: '#6f98c0',
    ring: 'rgba(111,152,192,0.2)',
  },
  [SystemMode.PROTECTION]: {
    title: '备电模式',
    desc: '优先保持关键负载供电',
    icon: Shield,
    accent: '#5ea58d',
    ring: 'rgba(94,165,141,0.2)',
  },
  [SystemMode.AI_FESOLAR]: {
    title: 'FeSolar AI',
    desc: '根据天气与负载自动调度',
    icon: Sparkles,
    accent: '#8c99c1',
    ring: 'rgba(140,153,193,0.2)',
  },
};

const historyRangeLabels: Record<HistoryRange, string> = {
  day: '日',
  week: '周',
  month: '月',
};

const App: React.FC = () => {
  const [activeUserId, setActiveUserId] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    const userId = parseUserIdFromPath(window.location.pathname);
    return userId && isValidTestUserId(userId) ? userId : null;
  });
  const [routeNotice, setRouteNotice] = useState('');
  const [isResourceUploadPage, setIsResourceUploadPage] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return (window.location.pathname || '') === RESOURCE_UPLOAD_PATH;
  });
  const [currentMode, setCurrentMode] = useState<SystemMode>(SystemMode.ECONOMIC);
  const [selectedComponent, setSelectedComponent] = useState<ComponentType | null>(null);
  const [powerData] = useState<ChartDataPoint[]>(generatePowerData());
  const [aiAdvice, setAiAdvice] = useState<string>('');
  const [isLoadingAi, setIsLoadingAi] = useState(false);
  const [isLoadingSuggestion, setIsLoadingSuggestion] = useState(false);
  const [suggestionBrief, setSuggestionBrief] = useState('');
  const [suggestionDetail, setSuggestionDetail] = useState('');
  const [suggestionError, setSuggestionError] = useState('');
  const [isAiChatOpen, setIsAiChatOpen] = useState(false);
  const [expandedChart, setExpandedChart] = useState<'power' | 'grid' | null>(null);
  const [historyMetric, setHistoryMetric] = useState<HistoryMetric | null>(null);
  const [historyRange, setHistoryRange] = useState<HistoryRange>('day');
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [healthError, setHealthError] = useState('');
  const [healthLoading, setHealthLoading] = useState(true);
  const [showUserPicker, setShowUserPicker] = useState(false);

  const [realtimeData, setRealtimeData] = useState<EnergyData>({
    solarPower: 4.2,
    gridPower: -1.5,
    batteryPower: 2.1,
    batteryLevel: 82,
    evPower: 7.4,
    homeLoad: 1.3,
    revenue: 12.5,
    timestamp: new Date().toISOString(),
  });

  const [pvForecast, setPvForecast] = useState<PVForecastData | null>(null);

  useEffect(() => {
    const syncRoute = () => {
      const pathname = window.location.pathname || '/';
      const candidate = parseUserIdFromPath(pathname);

      if (pathname === RESOURCE_UPLOAD_PATH) {
        setIsResourceUploadPage(true);
        setActiveUserId(null);
        setRouteNotice('');
        return;
      }

      if (pathname === '/' || pathname === '') {
        setIsResourceUploadPage(false);
        setActiveUserId(null);
        return;
      }

      if (candidate && isValidTestUserId(candidate)) {
        setIsResourceUploadPage(false);
        setActiveUserId(candidate);
        setRouteNotice('');
        return;
      }

      setIsResourceUploadPage(false);
      setActiveUserId(null);
      setRouteNotice('无效用户 ID，已返回用户池。');
      window.history.replaceState({}, '', '/');
    };

    syncRoute();
    window.addEventListener('popstate', syncRoute);
    return () => {
      window.removeEventListener('popstate', syncRoute);
    };
  }, []);

  const goToUserDashboard = (userId: string) => {
    if (!isValidTestUserId(userId)) return;
    setIsResourceUploadPage(false);
    setActiveUserId(userId);
    setSelectedComponent(null);
    setIsAiChatOpen(false);
    setRouteNotice('');
    const nextPath = `${USER_ROUTE_PREFIX}${encodeURIComponent(userId)}`;
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, '', nextPath);
    }
  };

  const goBackToUserPool = () => {
    setIsResourceUploadPage(false);
    setActiveUserId(null);
    setSelectedComponent(null);
    setIsAiChatOpen(false);
    if (window.location.pathname !== '/') {
      window.history.pushState({}, '', '/');
    }
  };

  const goToResourceUpload = () => {
    window.location.assign(WEB_STUDIO_PATH);
  };

  useEffect(() => {
    if (!activeUserId) {
      setAiAdvice('');
      setIsLoadingAi(false);
      return;
    }

    if (currentMode === SystemMode.AI_FESOLAR) {
      setIsLoadingAi(true);
      getFeSolarAdvice(realtimeData, currentMode, activeUserId).then((advice) => {
        setAiAdvice(advice);
        setIsLoadingAi(false);
      });
    } else {
      setAiAdvice('');
    }
  }, [activeUserId, currentMode]);

  useEffect(() => {
    // Always reset suggestion panel when user context changes.
    setIsLoadingSuggestion(false);
    setSuggestionBrief('');
    setSuggestionDetail('');
    setSuggestionError('');
  }, [activeUserId]);

  const requestSuggestion = async () => {
    if (!activeUserId || isLoadingSuggestion) {
      return;
    }
    setIsLoadingSuggestion(true);
    setSuggestionError('');
    try {
      const result = await generateSuggestion(activeUserId);
      const brief = String(result.brief || '').trim();
      const detail = String(result.detail || '').trim();
      setSuggestionBrief(brief || '未返回 brief');
      setSuggestionDetail(detail || '未返回 detail');
    } catch (error) {
      console.error('Failed to generate suggestion:', error);
      setSuggestionError(error instanceof Error ? error.message : '获取建议失败');
      setSuggestionBrief('');
      setSuggestionDetail('');
    } finally {
      setIsLoadingSuggestion(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const refreshForecast = async () => {
      const { fetchPVForecast } = await import('./services/pvService');
      const data = await fetchPVForecast();
      if (mounted) {
        setPvForecast(data);
      }
    };

    refreshForecast();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = expandedChart || historyMetric ? 'hidden' : previous || '';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [expandedChart, historyMetric]);

  useEffect(() => {
    let mounted = true;
    const fetchHealth = async () => {
      try {
        const response = await fetch('/api/v1/system-info', { method: 'GET' });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as HealthPayload;
        if (!mounted) return;
        setHealth(data || {});
        setHealthError('');
        setHealthLoading(false);
      } catch (error) {
        if (!mounted) return;
        setHealthError(error instanceof Error ? error.message : 'health unavailable');
        setHealthLoading(false);
      }
    };
    fetchHealth();
    const timer = window.setInterval(fetchHealth, 5000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  const activeModeMeta = modeTokens[currentMode];

  const statusPills: Array<{
    key: HistoryMetric;
    label: string;
    value: string;
    icon: React.ElementType;
    tone: string;
  }> = [
    { key: 'solar', label: '光伏', value: `${realtimeData.solarPower.toFixed(2)} kW`, icon: Leaf, tone: 'text-[#668fb7]' },
    { key: 'load', label: '家庭负载', value: `${realtimeData.homeLoad.toFixed(2)} kW`, icon: Activity, tone: 'text-[#7a8ca3]' },
    { key: 'battery', label: '电池', value: `${realtimeData.batteryLevel.toFixed(0)}%`, icon: Shield, tone: 'text-[#5ea58d]' },
    { key: 'ev', label: 'EV', value: `${realtimeData.evPower.toFixed(2)} kW`, icon: Sparkles, tone: 'text-[#8995bb]' },
  ];
  const statusCardPaint = [
    {
      bg: 'linear-gradient(150deg, rgba(247,252,255,0.86), rgba(228,240,252,0.58))',
      border: 'rgba(153,176,206,0.62)',
      value: '#4f7094',
    },
    {
      bg: 'linear-gradient(150deg, rgba(255,251,246,0.86), rgba(246,236,224,0.6))',
      border: 'rgba(213,190,160,0.58)',
      value: '#886f53',
    },
    {
      bg: 'linear-gradient(150deg, rgba(245,253,249,0.86), rgba(227,245,237,0.58))',
      border: 'rgba(140,189,170,0.56)',
      value: '#4e8b74',
    },
    {
      bg: 'linear-gradient(150deg, rgba(250,248,255,0.86), rgba(236,236,252,0.58))',
      border: 'rgba(169,172,214,0.56)',
      value: '#7179b3',
    },
  ];
  const historyPalette: Record<HistoryMetric, { stroke: string; areaStart: string; areaEnd: string; unit: string }> = {
    solar: { stroke: '#6f8eb1', areaStart: 'rgba(111,142,177,0.32)', areaEnd: 'rgba(111,142,177,0.03)', unit: 'kW' },
    load: { stroke: '#917551', areaStart: 'rgba(145,117,81,0.28)', areaEnd: 'rgba(145,117,81,0.03)', unit: 'kW' },
    battery: { stroke: '#55a087', areaStart: 'rgba(85,160,135,0.24)', areaEnd: 'rgba(85,160,135,0.03)', unit: '%' },
    ev: { stroke: '#747fbd', areaStart: 'rgba(116,127,189,0.26)', areaEnd: 'rgba(116,127,189,0.03)', unit: 'kW' },
  };

  const solarSeries = useMemo(
    () => powerData.map((point) => point.solar ?? point.solarPredicted ?? 0),
    [powerData]
  );

  const loadSeries = useMemo(() => powerData.map((point) => point.consumption), [powerData]);
  const solarPath = useMemo(() => buildLinePath(solarSeries, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING), [solarSeries]);
  const loadPath = useMemo(() => buildLinePath(loadSeries, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING), [loadSeries]);
  const solarAreaPath = useMemo(() => buildAreaPath(solarSeries, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING), [solarSeries]);
  const loadAreaPath = useMemo(() => buildAreaPath(loadSeries, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING), [loadSeries]);

  const gridSeries = useMemo(() => powerData.slice(-12), [powerData]);

  const forecastPeak = useMemo(() => {
    if (!pvForecast || !pvForecast.predictions.length) return '--';
    const value = Math.max(...pvForecast.predictions) / 1000;
    return value.toFixed(2);
  }, [pvForecast]);

  const forecastError = useMemo(() => {
    if (!pvForecast?.metrics?.MAPE && pvForecast?.metrics?.MAPE !== 0) return '--';
    return `${pvForecast.metrics.MAPE.toFixed(1)}%`;
  }, [pvForecast]);

  const gridPurchaseRatio = Math.max((realtimeData.gridPower / Math.max(realtimeData.homeLoad, 0.1)) * 100, 0);
  const previewSolarPath = useMemo(() => buildLinePath(solarSeries.slice(-12), 220, 64, 8), [solarSeries]);
  const previewLoadPath = useMemo(() => buildLinePath(loadSeries.slice(-12), 220, 64, 8), [loadSeries]);
  const gridPreview = useMemo(() => gridSeries.slice(-10), [gridSeries]);
  const historySeries = useMemo(() => {
    if (!historyMetric) return [] as Array<{ label: string; value: number }>;

    if (historyRange === 'day') {
      if (historyMetric === 'solar') {
        return powerData.map((point, index) => ({
          label: `${index}:00`,
          value: +(point.solar ?? point.solarPredicted ?? 0).toFixed(2),
        }));
      }

      if (historyMetric === 'load') {
        return powerData.map((point, index) => ({
          label: `${index}:00`,
          value: +point.consumption.toFixed(2),
        }));
      }

      if (historyMetric === 'battery') {
        return powerData.map((point, index) => ({
          label: `${index}:00`,
          value: +point.battery.toFixed(0),
        }));
      }

      const evBase = Math.max(realtimeData.evPower, 0.6);
      return powerData.map((_, index) => {
        const hour = index;
        const chargingFactor = hour >= 20 || hour <= 6 ? 1.14 : 0.82;
        const drift = 0.9 + Math.sin(index * 0.65) * 0.1;
        return {
          label: `${index}:00`,
          value: +(evBase * chargingFactor * drift).toFixed(2),
        };
      });
    }

    const periods = historyRange === 'week' ? 7 : 30;
    const base =
      historyMetric === 'solar'
        ? Math.max(realtimeData.solarPower, 0.8)
        : historyMetric === 'load'
          ? Math.max(realtimeData.homeLoad, 0.6)
          : historyMetric === 'battery'
            ? Math.max(realtimeData.batteryLevel, 20)
            : Math.max(realtimeData.evPower, 0.6);

    return Array.from({ length: periods }, (_, index) => {
      const x = index / Math.max(periods - 1, 1);
      let value = base * (0.86 + Math.sin(x * Math.PI * 2.2) * 0.15 + Math.cos(x * Math.PI * 4.1) * 0.08);
      if (historyMetric === 'battery') {
        value = Math.min(100, Math.max(18, value));
      } else {
        value = Math.max(0, value);
      }

      return {
        label: historyRange === 'week' ? `周${index + 1}` : `${index + 1}日`,
        value: +value.toFixed(historyMetric === 'battery' ? 0 : 2),
      };
    });
  }, [historyMetric, historyRange, powerData, realtimeData.batteryLevel, realtimeData.evPower, realtimeData.homeLoad, realtimeData.solarPower]);

  const historyValues = useMemo(() => historySeries.map((point) => point.value), [historySeries]);
  const historyLinePath = useMemo(
    () => buildLinePath(historyValues, HISTORY_CHART_WIDTH, HISTORY_CHART_HEIGHT, HISTORY_CHART_PADDING),
    [historyValues]
  );
  const historyAreaPath = useMemo(
    () => buildAreaPath(historyValues, HISTORY_CHART_WIDTH, HISTORY_CHART_HEIGHT, HISTORY_CHART_PADDING),
    [historyValues]
  );
  const historyStats = useMemo(() => {
    if (!historyValues.length) return { max: 0, min: 0, avg: 0 };
    const max = Math.max(...historyValues);
    const min = Math.min(...historyValues);
    const avg = historyValues.reduce((acc, value) => acc + value, 0) / historyValues.length;
    return { max, min, avg };
  }, [historyValues]);
  const historyMeta = useMemo(() => statusPills.find((pill) => pill.key === historyMetric) || null, [historyMetric, statusPills]);
  const historyColor = historyMetric ? historyPalette[historyMetric] : null;
  const formatHistoryValue = (metric: HistoryMetric, value: number) =>
    metric === 'battery' ? `${value.toFixed(0)}%` : `${value.toFixed(2)} kW`;

  if (!activeUserId && isResourceUploadPage) {
    return <KnowledgeUploadPage onBack={goBackToUserPool} />;
  }

  if (!activeUserId) {
    const statusOk = Boolean(health?.ready);
    return (
      <div className="min-h-screen bg-slate-100 text-slate-900">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <header className="mb-6 rounded-2xl bg-white p-6 shadow-sm">
            <h1 className="text-3xl font-bold tracking-tight">FLS-Agent 管理后台</h1>
            <p className="mt-2 text-sm text-slate-600">系统状态监控、知识库管理、Agent 测试入口</p>
            {routeNotice ? <div className="mt-3 text-xs text-amber-700">{routeNotice}</div> : null}
          </header>

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
            <div className="rounded-2xl bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center gap-2 text-lg font-semibold">
                <Activity size={18} />
                系统状态看板
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-500">系统状态</div>
                  <div className={`mt-2 text-2xl font-bold ${statusOk ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {healthLoading ? '加载中...' : statusOk ? '正常' : '异常'}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-500">排队用户数</div>
                  <div className="mt-2 text-2xl font-bold text-sky-700">{String(health?.concurrency?.queued_users ?? '-')}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-500">排队请求数</div>
                  <div className="mt-2 text-2xl font-bold text-indigo-700">{String(health?.concurrency?.queued_requests ?? '-')}</div>
                </div>
              </div>
              {healthError ? <div className="mt-4 text-xs text-rose-600">状态获取失败: {healthError}</div> : null}
            </div>

            <div className="space-y-4">
              <button
                type="button"
                onClick={goToResourceUpload}
                className="w-full rounded-2xl bg-white p-5 text-left shadow-sm transition hover:shadow-md"
              >
                <div className="text-lg font-semibold">知识库管理</div>
                <div className="mt-1 text-sm text-slate-600">进入知识库上传页面</div>
              </button>
              <button
                type="button"
                onClick={() => setShowUserPicker(true)}
                className="w-full rounded-2xl bg-white p-5 text-left shadow-sm transition hover:shadow-md"
              >
                <div className="text-lg font-semibold">Agent 测试</div>
                <div className="mt-1 text-sm text-slate-600">选择测试用户并进入完整页面</div>
              </button>
            </div>
          </section>

          <section className="mt-6">
            <BatchQuestionTestPanel />
          </section>
        </div>

        {showUserPicker ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowUserPicker(false)}>
            <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl" onClick={(event) => event.stopPropagation()}>
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xl font-semibold">选择测试用户</h2>
                <button type="button" onClick={() => setShowUserPicker(false)} className="rounded-md p-1 hover:bg-slate-100">
                  <XCircle className="h-5 w-5 text-slate-500" />
                </button>
              </div>
              <div className="grid grid-cols-4 gap-2 sm:grid-cols-5">
                {TEST_USER_IDS.map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => goToUserDashboard(id)}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    User {id}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden px-5 py-5 text-[color:var(--ink-strong)] selection:bg-[#dbe8f6] md:px-8 md:py-6">
      <div className="pointer-events-none absolute -left-10 top-6 h-[24rem] w-[24rem] rounded-full bg-[#fff6e8]/76 blur-3xl" />
      <div className="pointer-events-none absolute right-0 top-0 h-[26rem] w-[26rem] rounded-full bg-[#d7e6f9]/62 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-[#e0edf9]/56 blur-3xl" />

      <div className="relative mx-auto flex w-full max-w-[1660px] flex-col gap-5">
        <header className="glass-hero rounded-[40px] px-5 py-5 md:px-8 md:py-6">
          <div className="flex flex-col gap-5 2xl:flex-row 2xl:items-center 2xl:justify-between">
            <div className="max-w-[780px]">
              <div className="mb-3 flex items-center gap-2">
                <button
                  onClick={goBackToUserPool}
                  type="button"
                  className="glass-chip inline-flex items-center gap-1 rounded-full border border-[#c3d3e8]/78 bg-white/60 px-3 py-1.5 text-xs font-semibold text-[#6d84a2] transition-colors hover:bg-white/75"
                >
                  <ArrowLeft size={13} />
                  返回用户池
                </button>
                <span className="glass-chip inline-flex items-center gap-1 rounded-full border border-[#bfd0e6]/70 bg-white/55 px-3 py-1.5 text-xs font-semibold text-[#627997]">
                  当前用户 {activeUserId}
                </span>
              </div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[#bfd0e6]/70 bg-white/54 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.16em] text-[#6d82a1]">
                <span className="h-2 w-2 rounded-full bg-[#8db09c] pulse-soft" />
                Home Energy Digital Twin
              </div>
              <h1 className="font-heading text-4xl font-bold leading-tight text-[#324358] md:text-5xl">FeSolar Home</h1>
            </div>

            <div className="grid w-full max-w-[500px] grid-cols-1 gap-3 sm:grid-cols-2">
              <div
                className="glass-chip rounded-2xl px-4 py-3"
                style={{ background: 'linear-gradient(145deg, rgba(247,252,255,0.78), rgba(228,238,250,0.54))' }}
              >
                <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-[#7286a4]">
                  <CloudSun size={14} />
                  Environment
                </div>
                <div className="text-sm font-semibold text-[#41546c]">上海 徐汇 · 晴间多云</div>
                <div className="mt-1 flex items-center gap-4 text-xs text-[#6f8096]">
                  <span className="inline-flex items-center gap-1">
                    <ThermometerSun size={13} /> 26°C
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Wind size={13} /> 5.2m/s
                  </span>
                </div>
              </div>

              <div
                className="glass-chip rounded-2xl px-4 py-3"
                style={{ background: 'linear-gradient(145deg, rgba(250,249,255,0.82), rgba(232,236,252,0.56))' }}
              >
                <div className="mb-1 flex items-center justify-between text-xs font-semibold uppercase tracking-widest text-[#7286a4]">
                  <span>System</span>
                  <Bell size={14} />
                </div>
                <div className="text-sm font-semibold text-[#41546c]">最近刷新 {formatTime(realtimeData.timestamp)}</div>
                <div className="mt-1 text-xs text-[#6f8096]">当前模式：{activeModeMeta.title}</div>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2.5">
            {(Object.keys(modeTokens) as SystemMode[]).map((mode) => {
              const modeMeta = modeTokens[mode];
              const active = currentMode === mode;
              const Icon = modeMeta.icon;

              return (
                <button
                  key={mode}
                  onClick={() => setCurrentMode(mode)}
                  className="glass-chip inline-flex cursor-pointer items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold text-[#63748a] transition-[transform,box-shadow,border-color,background-color] duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:scale-[1.01]"
                  style={{
                    borderColor: active ? modeMeta.accent : 'rgba(184,199,218,0.78)',
                    background: active
                      ? `linear-gradient(145deg, ${modeMeta.ring}, rgba(255,255,255,0.62))`
                      : 'linear-gradient(145deg, rgba(255,255,255,0.56), rgba(240,246,253,0.44))',
                  }}
                >
                  <span
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-white"
                    style={{ background: active ? modeMeta.accent : 'rgba(130,151,177,0.3)' }}
                  >
                    <Icon size={14} />
                  </span>
                  {modeMeta.title}
                </button>
              );
            })}
          </div>
        </header>

        <section className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_320px]">
          <main className="flex min-w-0 flex-col gap-5">
            <div className="glass-card rounded-[36px] p-4 md:p-5">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-[#778aa8]">Realtime Energy Stage</div>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="glass-chip rounded-lg px-2.5 py-1 text-[#6d88ad]">峰值 {forecastPeak} kW</span>
                  <span className="glass-chip rounded-lg px-2.5 py-1 text-[#6e9d89]">预测误差 {forecastError}</span>
                  <span className="glass-chip rounded-lg px-2.5 py-1 text-[#8769a1]">购电占比 {gridPurchaseRatio.toFixed(0)}%</span>
                </div>
              </div>

              <div className="relative overflow-hidden rounded-[32px] border border-[#bfd0e4]/58 bg-[linear-gradient(160deg,rgba(255,255,255,0.62),rgba(236,244,252,0.42))] p-1 md:p-2">
                <IsoHouse onSelectComponent={setSelectedComponent} data={realtimeData} />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              {statusPills.map((pill, index) => {
                const PillIcon = pill.icon;
                const paint = statusCardPaint[index];
                return (
                  <button
                    key={pill.label}
                    type="button"
                    onClick={() => {
                      setHistoryMetric(pill.key);
                      setHistoryRange('day');
                    }}
                    className="cursor-pointer rounded-3xl border px-5 py-5 text-left shadow-[0_12px_26px_rgba(92,109,132,0.13)] transition-[transform,box-shadow] duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(92,109,132,0.18)]"
                    style={{
                      background: paint.bg,
                      borderColor: paint.border,
                    }}
                    aria-label={`查看${pill.label}日周月历史数据`}
                  >
                    <div className={`inline-flex items-center gap-1 text-xs font-semibold ${pill.tone}`}>
                      <PillIcon size={13} />
                      {pill.label}
                    </div>
                    <div className="mt-3 text-3xl font-bold" style={{ color: paint.value }}>
                      {pill.value}
                    </div>
                    <div className="mt-2 text-xs text-[#7b8ea5]">点击查看日 / 周 / 月历史</div>
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <button
                onClick={() => setExpandedChart('power')}
                className="glass-card group cursor-pointer rounded-3xl p-5 text-left transition-[transform,box-shadow,border-color,background-color] duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:scale-[1.008] hover:shadow-[0_18px_38px_rgba(96,113,137,0.2)]"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="mb-1 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#7589a7]">
                      <LineChart size={14} />
                      功率趋势
                    </div>
                    <div className="text-lg font-bold text-[#3c5068]">Solar vs Home Load</div>
                    <div className="mt-1 text-sm text-[#6e8096]">默认折叠，点击查看完整 24h 曲线与面积层。</div>
                  </div>
                  <ChevronRight size={18} className="mt-1 text-[#7b90ae] transition-transform duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:translate-x-1" />
                </div>

                <div className="mt-4 overflow-hidden rounded-2xl border border-[#bfd0e4]/65 bg-white/45 p-2">
                  <svg viewBox="0 0 220 64" className="h-16 w-full">
                    <path d={previewLoadPath} fill="none" stroke="#76a08d" strokeWidth={2.1} strokeLinecap="round" />
                    <path d={previewSolarPath} fill="none" stroke="#6f8eb1" strokeWidth={2.1} strokeLinecap="round" />
                  </svg>
                </div>
              </button>

              <button
                onClick={() => setExpandedChart('grid')}
                className="glass-card group cursor-pointer rounded-3xl p-5 text-left transition-[transform,box-shadow,border-color,background-color] duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:scale-[1.008] hover:shadow-[0_18px_38px_rgba(96,113,137,0.2)]"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="mb-1 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#7589a7]">
                      <BarChart3 size={14} />
                      Grid Exchange
                    </div>
                    <div className="text-lg font-bold text-[#3c5068]">近12小时买电 / 回馈</div>
                    <div className="mt-1 text-sm text-[#6e8096]">默认折叠，点击查看分时柱状与交换峰值。</div>
                  </div>
                  <ChevronRight size={18} className="mt-1 text-[#7b90ae] transition-transform duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:translate-x-1" />
                </div>

                <div className="mt-4 flex h-16 items-end gap-1 rounded-2xl border border-[#bfd0e4]/65 bg-white/42 px-2 py-2">
                  {gridPreview.map((point) => {
                    const magnitude = Math.min(Math.abs(point.grid) / 5, 1);
                    const h = 8 + magnitude * 42;
                    const isImport = point.grid >= 0;
                    return (
                      <span
                        key={point.time}
                        className="flex-1 rounded-sm"
                        style={{
                          height: `${h}px`,
                          background: isImport
                            ? 'linear-gradient(180deg, rgba(110,145,184,0.9), rgba(87,121,160,0.82))'
                            : 'linear-gradient(180deg, rgba(102,164,142,0.9), rgba(81,140,119,0.82))',
                        }}
                      />
                    );
                  })}
                </div>
              </button>
            </div>
          </main>

          <aside className="flex flex-col gap-4">
            <div
              className="glass-card rounded-[30px] p-5"
              style={{ background: 'linear-gradient(156deg, rgba(246,252,255,0.8), rgba(231,240,252,0.56))' }}
            >
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="glass-chip flex h-10 w-10 items-center justify-center rounded-full text-[#5f7ea2]">
                    <User size={18} />
                  </div>
                  <div>
                    <div className="font-heading text-sm font-bold text-[#3d5067]">{activeUserId}</div>
                    <div className="text-xs text-[#6f8197]">测试用户</div>
                  </div>
                </div>
                <button className="rounded-lg p-2 text-[#8094af] transition-colors hover:bg-white/45" aria-label="退出登录">
                  <LogOut size={15} />
                </button>
              </div>

              <div
                className="glass-chip rounded-xl p-3"
                style={{ background: 'linear-gradient(145deg, rgba(244,250,255,0.82), rgba(229,238,250,0.58))' }}
              >
                <div className="mb-1 inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-widest text-[#5f7ea2]">
                  <Sparkles size={12} />
                  家庭策略状态
                </div>
                <p className="text-sm leading-relaxed text-[#607289]">
                  {currentMode === SystemMode.AI_FESOLAR
                    ? isLoadingAi
                      ? 'AI 正在分析实时负载与天气变化...'
                      : aiAdvice || 'AI 将在下一轮数据更新后给出策略建议。'
                    : `当前为 ${activeModeMeta.title}，系统按家庭偏好稳定运行。`}
                </p>
              </div>

              <div className="mt-3">
                <button
                  type="button"
                  onClick={requestSuggestion}
                  disabled={isLoadingSuggestion}
                  className="inline-flex items-center rounded-lg border border-[#becde0] bg-white/70 px-3 py-2 text-xs font-semibold text-[#4f6480] transition-colors hover:bg-white/85 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isLoadingSuggestion ? '获取建议中...' : '获取建议'}
                </button>
              </div>

              {suggestionError ? (
                <div className="mt-3 rounded-lg border border-[#e9c8bf] bg-[#fff5f2]/80 px-3 py-2 text-xs text-[#9b5a4d]">
                  {suggestionError}
                </div>
              ) : null}

              {suggestionBrief || suggestionDetail ? (
                <div className="mt-3 rounded-xl border border-[#bfd0e4]/70 bg-white/55 p-3">
                  <div className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#5f7ea2]">Suggestion Brief</div>
                  <div className="mt-1 text-sm font-semibold text-[#425a75] whitespace-pre-wrap">{suggestionBrief || '--'}</div>
                  <div className="mt-3 text-[11px] font-bold uppercase tracking-[0.12em] text-[#5f7ea2]">Suggestion Detail</div>
                  <div className="mt-1 text-xs leading-relaxed text-[#5d738f] whitespace-pre-wrap">{suggestionDetail || '--'}</div>
                </div>
              ) : null}
            </div>

            <button
              onClick={() => setIsAiChatOpen(true)}
              className="glass-card group cursor-pointer rounded-[30px] border-[#b2bde6] p-5 text-left transition-[transform,box-shadow,border-color,background-color] duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:scale-[1.012] hover:shadow-[0_22px_44px_rgba(102,111,186,0.28)]"
              style={{ background: 'linear-gradient(145deg, rgba(240,243,255,0.96), rgba(227,235,255,0.82) 44%, rgba(223,238,252,0.74))' }}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div
                    className="glass-chip flex h-11 w-11 items-center justify-center rounded-full text-[#5f6bc2]"
                    style={{ background: 'linear-gradient(145deg, rgba(232,236,255,0.94), rgba(213,224,255,0.76))' }}
                  >
                    <Bot size={19} />
                  </div>
                  <div>
                    <div className="font-heading text-[15px] font-bold text-[#4d57ae]">FeSolar 家庭助手</div>
                    <div className="text-xs text-[#6673ad]">能源诊断 · 设备协同 · 策略问答</div>
                  </div>
                </div>
                <div className="inline-flex items-center gap-1 rounded-full border border-[#b9c2ea] bg-white/52 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6570b4]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#7a85d1] pulse-soft" />
                  Assistant
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] font-semibold">
                <div className="rounded-lg border border-[#bec7ec] bg-white/52 px-3 py-2 text-[#5d67ab]">负载异常解读</div>
                <div className="rounded-lg border border-[#bec7ec] bg-white/52 px-3 py-2 text-[#5d67ab]">最佳充放电时段</div>
              </div>

              <div className="mt-4 flex items-center justify-between">
                <div className="text-xs text-[#6d78ad]">在线 · 平均响应 2s</div>
                <div
                  className="glass-chip rounded-lg p-2 text-[#6972b8]"
                  style={{ background: 'linear-gradient(145deg, rgba(236,234,255,0.9), rgba(219,225,252,0.7))' }}
                >
                  <MessageSquare size={15} />
                </div>
              </div>
            </button>

            <div
              className="glass-card rounded-[30px] p-5"
              style={{ background: 'linear-gradient(156deg, rgba(255,251,244,0.86), rgba(248,239,225,0.6))' }}
            >
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-[#a07a4e]">
                <AlertTriangle size={14} />
                今日提醒
              </div>
              <ul className="space-y-2 text-xs text-[#7f6a52]">
                <li className="glass-chip rounded-lg px-3 py-2" style={{ background: 'rgba(255, 248, 237, 0.76)' }}>
                  12:30 电网电压短时升高，已自动柔性限流。
                </li>
                <li className="glass-chip rounded-lg px-3 py-2" style={{ background: 'rgba(255, 248, 237, 0.76)' }}>
                  17:00 光伏预计回落，建议提前给电池补能。
                </li>
              </ul>
            </div>
          </aside>
        </section>

      </div>

      {historyMetric && historyMeta && historyColor ? (
        <div className="fixed inset-0 z-[136] flex items-center justify-center bg-[rgba(71,90,116,0.24)] p-4" onClick={() => setHistoryMetric(null)}>
          <div
            className="glass-hero panel-enter w-full max-w-[1080px] rounded-[34px] p-5 shadow-[0_36px_90px_rgba(87,106,130,0.26)] md:p-6"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="历史数据视图"
          >
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-heading text-xl font-bold text-[#3a4f68]">{historyMeta.label} 历史数据</div>
                <p className="text-sm text-[#70829a]">按日 / 周 / 月查看趋势变化</p>
              </div>
              <div className="flex items-center gap-2">
                {(Object.keys(historyRangeLabels) as HistoryRange[]).map((range) => (
                  <button
                    key={range}
                    type="button"
                    onClick={() => setHistoryRange(range)}
                    className="rounded-lg border px-3 py-1.5 text-sm font-semibold transition-colors"
                    style={{
                      borderColor: historyRange === range ? historyColor.stroke : 'rgba(183,197,215,0.72)',
                      background: historyRange === range ? 'rgba(255,255,255,0.72)' : 'rgba(255,255,255,0.42)',
                      color: historyRange === range ? historyColor.stroke : '#6e8097',
                    }}
                  >
                    {historyRangeLabels[range]}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setHistoryMetric(null)}
                  className="glass-chip rounded-lg p-2 text-[#768ba9] transition-colors hover:bg-white/60"
                  aria-label="关闭历史数据"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-[#bfd0e4]/72 bg-white/46 p-3">
              <svg viewBox={`0 0 ${HISTORY_CHART_WIDTH} ${HISTORY_CHART_HEIGHT}`} className="h-[320px] min-w-[760px] w-full">
                <defs>
                  <linearGradient id="historyAreaFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={historyColor.areaStart} />
                    <stop offset="100%" stopColor={historyColor.areaEnd} />
                  </linearGradient>
                </defs>

                <rect x="0" y="0" width={HISTORY_CHART_WIDTH} height={HISTORY_CHART_HEIGHT} rx="16" fill="rgba(255,255,255,0.44)" />
                {[0, 1, 2, 3].map((idx) => {
                  const y = HISTORY_CHART_PADDING + (idx / 3) * (HISTORY_CHART_HEIGHT - HISTORY_CHART_PADDING * 2);
                  return (
                    <line
                      key={idx}
                      x1={HISTORY_CHART_PADDING}
                      y1={y}
                      x2={HISTORY_CHART_WIDTH - HISTORY_CHART_PADDING}
                      y2={y}
                      stroke="rgba(138,159,184,0.34)"
                      strokeDasharray="4 7"
                    />
                  );
                })}

                <path d={historyAreaPath} fill="url(#historyAreaFill)" />
                <path d={historyLinePath} fill="none" stroke={historyColor.stroke} strokeWidth={2.8} strokeLinecap="round" />

                {historySeries.map((point, index) => {
                  const showLabel =
                    (historyRange === 'day' && (index % 4 === 0 || index === historySeries.length - 1)) ||
                    historyRange === 'week' ||
                    (historyRange === 'month' && (index % 5 === 0 || index === historySeries.length - 1));

                  if (!showLabel) return null;

                  const x =
                    HISTORY_CHART_PADDING +
                    (index / Math.max(historySeries.length - 1, 1)) * (HISTORY_CHART_WIDTH - HISTORY_CHART_PADDING * 2);

                  return (
                    <text key={point.label} x={x} y={HISTORY_CHART_HEIGHT - 6} textAnchor="middle" fontSize={10} fill="#7588a3" fontWeight={700}>
                      {point.label}
                    </text>
                  );
                })}
              </svg>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="glass-chip rounded-xl p-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-[#71839b]">最大值</div>
                <div className="mt-1 text-xl font-bold" style={{ color: historyColor.stroke }}>
                  {formatHistoryValue(historyMetric, historyStats.max)}
                </div>
              </div>
              <div className="glass-chip rounded-xl p-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-[#71839b]">最小值</div>
                <div className="mt-1 text-xl font-bold" style={{ color: historyColor.stroke }}>
                  {formatHistoryValue(historyMetric, historyStats.min)}
                </div>
              </div>
              <div className="glass-chip rounded-xl p-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-[#71839b]">平均值</div>
                <div className="mt-1 text-xl font-bold" style={{ color: historyColor.stroke }}>
                  {formatHistoryValue(historyMetric, historyStats.avg)}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {expandedChart ? (
        <div className="fixed inset-0 z-[135] flex items-center justify-center bg-[rgba(71,90,116,0.24)] p-4" onClick={() => setExpandedChart(null)}>
          <div
            className="glass-hero panel-enter w-full max-w-[1060px] rounded-[34px] p-5 shadow-[0_36px_90px_rgba(87,106,130,0.26)] md:p-6"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="图表展开视图"
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="font-heading text-xl font-bold text-[#3a4f68]">{expandedChart === 'power' ? '24小时功率趋势' : '电网交换近12小时'}</div>
                <p className="text-sm text-[#70829a]">{expandedChart === 'power' ? '光伏发电与家庭负载时序对比' : '正值为购电，负值为回馈'}</p>
              </div>
              <button
                onClick={() => setExpandedChart(null)}
                className="glass-chip rounded-lg p-2 text-[#768ba9] transition-colors hover:bg-white/60"
                aria-label="关闭图表"
              >
                <X size={16} />
              </button>
            </div>

            {expandedChart === 'power' ? (
              <div className="overflow-x-auto rounded-2xl border border-[#bfd0e4]/72 bg-white/46 p-3">
                <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="h-[330px] min-w-[720px] w-full">
                  <defs>
                    <linearGradient id="powerSolarAreaWarm" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6f8eb1" stopOpacity="0.34" />
                      <stop offset="100%" stopColor="#6f8eb1" stopOpacity="0.02" />
                    </linearGradient>
                    <linearGradient id="powerLoadAreaWarm" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#64a18c" stopOpacity="0.24" />
                      <stop offset="100%" stopColor="#64a18c" stopOpacity="0.02" />
                    </linearGradient>
                  </defs>

                  <rect x="0" y="0" width={CHART_WIDTH} height={CHART_HEIGHT} rx="16" fill="rgba(255,255,255,0.42)" />
                  {[0, 1, 2, 3].map((idx) => {
                    const y = CHART_PADDING + (idx / 3) * (CHART_HEIGHT - CHART_PADDING * 2);
                    return (
                      <line
                        key={idx}
                        x1={CHART_PADDING}
                        y1={y}
                        x2={CHART_WIDTH - CHART_PADDING}
                        y2={y}
                        stroke="rgba(138,159,184,0.35)"
                        strokeDasharray="4 7"
                      />
                    );
                  })}
                  <path d={loadAreaPath} fill="url(#powerLoadAreaWarm)" />
                  <path d={solarAreaPath} fill="url(#powerSolarAreaWarm)" />
                  <path d={loadPath} fill="none" stroke="#64a18c" strokeWidth={2.8} strokeLinecap="round" />
                  <path d={solarPath} fill="none" stroke="#6f8eb1" strokeWidth={2.8} strokeLinecap="round" />
                </svg>
              </div>
            ) : (
              <div className="rounded-2xl border border-[#bfd0e4]/72 bg-white/46 p-4">
                <div className="flex h-[330px] items-end gap-2">
                  {gridSeries.map((point) => {
                    const magnitude = Math.min(Math.abs(point.grid) / 5, 1);
                    const h = 26 + magnitude * 240;
                    const isImport = point.grid >= 0;
                    return (
                      <div key={point.time} className="flex flex-1 flex-col items-center justify-end gap-2">
                        <div
                          className="w-full rounded-t-md"
                          style={{
                            height: `${h}px`,
                            background: isImport
                              ? 'linear-gradient(180deg, rgba(110,145,184,0.95), rgba(87,121,160,0.88))'
                              : 'linear-gradient(180deg, rgba(100,161,140,0.95), rgba(78,138,118,0.9))',
                          }}
                        />
                        <div className="text-[10px] font-semibold text-[#72829a]">{point.time.split(':')[0]}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      <AiChatPanel key={activeUserId} isOpen={isAiChatOpen} onClose={() => setIsAiChatOpen(false)} userId={activeUserId} />
      <SettingsPanel component={selectedComponent} onClose={() => setSelectedComponent(null)} />
    </div>
  );
};

export default App;
