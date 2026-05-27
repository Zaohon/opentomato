import React, { useState, useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, ReferenceLine, Cell, ComposedChart, Line } from 'recharts';
import { ChartDataPoint, TimeRange, PVForecastData } from '../types';
import { Maximize2, X, Calendar, ChevronDown } from 'lucide-react';

interface ChartsPanelProps {
  powerData: ChartDataPoint[];
  pvForecast: PVForecastData | null;
  selectedDay?: number;
  onDateSelect?: (day: number) => void;
}

// Helper to generate mock week/month data for the expanded view
const generateExtendedData = (range: TimeRange, baseData: ChartDataPoint[]): any[] => {
  if (range === 'DAY') return baseData;

  if (range === 'WEEK') {
    const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return days.map(day => ({
      time: day,
      solar: +(Math.random() * 30 + 10).toFixed(1),
      consumption: +(Math.random() * 20 + 10).toFixed(1),
      battery: +(Math.random() * 100).toFixed(0),
      grid: +(Math.random() * 20 - 10).toFixed(1)
    }));
  }

  if (range === 'MONTH') {
    return Array.from({ length: 15 }, (_, i) => ({
      time: `${i * 2 + 1}日`,
      solar: +(Math.random() * 40 + 10).toFixed(1),
      consumption: +(Math.random() * 30 + 10).toFixed(1),
      battery: +(Math.random() * 100).toFixed(0),
      grid: +(Math.random() * 25 - 12).toFixed(1)
    }));
  }

  if (range === 'YEAR') {
    return ['1月', '2月', '3月', '4月', '5月'].map(m => ({
      time: m,
      solar: 120,
      consumption: 100,
      battery: 80,
      grid: 10
    }));
  }

  return baseData;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    // Translate labels in tooltip dynamically if needed, or rely on chart definition
    const mapName = (name: string) => {
      if (name === "Solar Output") return "光伏产出";
      if (name === "Daily Generation") return "日光伏发电";
      if (name === "Prediction (AI)") return "AI 预测";
      if (name === "Charge Level") return "电量水平";
      if (name === "Consumption") return "能耗";
      if (name === "Net Grid") return "电网净值";
      return name;
    }

    return (
      <div className="glass-panel-dark p-3 rounded-xl border border-white/10 text-xs z-50 shadow-2xl backdrop-blur-3xl bg-slate-900/90">
        <p className="font-bold text-gray-200 mb-2 border-b border-white/10 pb-1">{label}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center justify-between gap-4 mb-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.stroke || entry.fill }}></span>
              <span className="text-gray-400 font-medium">{mapName(entry.name)}:</span>
            </div>
            <span className="text-white font-bold">
              {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value} {entry.name.includes('Level') || entry.name.includes('Charge') ? '%' : 'kW'}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

const ChartsPanel: React.FC<ChartsPanelProps> = ({ powerData, pvForecast, selectedDay = 16, onDateSelect }) => {
  const [expandedChart, setExpandedChart] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('DAY');

  // Derive data based on selected range (mock logic)
  const expandedData = useMemo(() => {
    return generateExtendedData(timeRange, powerData);
  }, [timeRange, powerData]);

  // Memoize calendar heatmap data to prevent flickering on re-renders
  const calendarDays = useMemo(() => {
    return Array.from({ length: 30 }).map((_, i) => {
      const day = i + 1;
      // Mock heatmap logic
      let opacity = 0;
      let isActive = false;

      if (day === selectedDay) {
        isActive = true;
        opacity = 1;
      } else if (day < (selectedDay || 16)) {
        // Random opacity for past days (0.1 to 0.6)
        opacity = 0.1 + Math.random() * 0.5;
      }

      return { day, opacity, isActive };
    });
  }, [selectedDay]);

  // Handler for closing the expanded view
  const closeExpanded = (e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedChart(null);
    setTimeRange('DAY'); // Reset
  };

  // Render the expanded overlay content
  const renderExpandedContent = () => {
    if (!expandedChart) return null;

    let chartTitle = '';
    let color = '';
    let ChartComponent = null;

    // Config based on type
    if (expandedChart === 'SOLAR') {
      chartTitle = '光伏发电预测';
      // If we have real forecast data, use it; otherwise fallback to mock
      const hasForecast = !!pvForecast;

      const chartData = hasForecast ? pvForecast!.times.map((t, i) => {
        const date = new Date(t);
        const timeStr = Number.isNaN(date.getTime())
          ? '--:--'
          : date.toLocaleTimeString('zh-CN', {
              hour: '2-digit',
              minute: '2-digit',
              timeZone: 'Asia/Shanghai',
            });

        return {
          time: timeStr,
          solarPredicted: pvForecast!.predictions[i], // Value is already in W
          solarActual: pvForecast!.actuals[i], // Value is already in W
          // Store adjusted full date string if needed, or just use original for debug
          fullTime: Number.isNaN(date.getTime())
            ? t
            : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
        };
      }) : expandedData.map(d => ({
        ...d,
        solarPredicted: d.solarPredicted || (d.solar || 0), // Mock data fallback
        solarActual: d.solar || 0
      }));

      // Calculate Metrics for Sidebar
      const totalGenWh = chartData.reduce((acc, curr) => acc + (curr.solarPredicted || 0), 0);
      const totalGenKwh = (totalGenWh / 1000).toFixed(1);

      const peakPower = Math.max(...chartData.map(d => d.solarPredicted || 0)).toFixed(0);



      ChartComponent = (
        <div className="flex w-full h-full gap-8">
          {/* Chart Area */}
          <div className="flex-1 w-full bg-slate-900/30 rounded-3xl border border-white/5 p-4 shadow-inner relative overflow-hidden group">
            {/* Subtle Tech Grid Background */}
            <div className="absolute inset-0 z-0 opacity-10" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)', backgroundSize: '40px 40px' }}></div>

            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorSolarPred" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorSolarAct" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} unit=" W" />
                <Tooltip content={<CustomTooltip />} />

                <Area
                  name="实际发电与真实值"
                  type="monotone"
                  dataKey={hasForecast ? "solarActual" : "solar"}
                  stroke="#f59e0b"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#colorSolarAct)"
                />
                <Area
                  name="未来预测值"
                  type="monotone"
                  dataKey="solarPredicted"
                  stroke="#06b6d4"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#colorSolarPred)"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Sidebar Info */}
          <div className="w-80 flex flex-col gap-6 animate-in slide-in-from-right-10 duration-500 delay-100">

            {/* Heatmap Card (Real Calendar View) */}
            <div className="glass-panel-dark p-3 rounded-3xl relative overflow-hidden group flex flex-col h-auto">
              <div className="flex justify-between items-center mb-1">
                <div className="text-xs text-amber-500 font-bold uppercase tracking-widest">
                  2025年9月 发电量日历
                </div>
                <Calendar size={16} className="text-slate-500" />
              </div>

              {/* Calendar Grid - Sep 2025 (Starts Monday, 30 days) */}
              <div className="flex-1 flex flex-col">
                {/* Weekday Headers */}
                <div className="grid grid-cols-7 text-center mb-1">
                  {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
                    <div key={i} className="text-[9px] text-slate-600 font-bold">{d}</div>
                  ))}
                </div>

                {/* Days */}
                <div className="grid grid-cols-7 gap-px text-center">
                  {/* Sep 1 2025 is Monday, so 1 empty slot for Sunday */}
                  <div />

                  {/* Real Days - Heatmap */}
                  {calendarDays.map(({ day, opacity, isActive }) => (
                    <div key={day} className="flex items-center justify-center py-0.5 relative">
                      <div
                        onClick={() => onDateSelect?.(day)}
                        className={`w-5 h-5 rounded-sm flex items-center justify-center text-[9px] border transition-all cursor-pointer hover:border-amber-400/50
                          ${isActive
                            ? 'bg-amber-500 text-slate-900 border-amber-400 font-bold shadow-[0_0_10px_rgba(245,158,11,0.5)] scale-110 z-10'
                            : day < (selectedDay || 16)
                              ? 'text-amber-100 border-transparent hover:bg-white/10'
                              : 'bg-white/5 text-slate-600 border-white/5 hover:bg-white/10'
                          }`}
                        style={!isActive && day < (selectedDay || 16) ? { backgroundColor: `rgba(245, 158, 11, ${opacity})` } : {}}
                      >
                        {day}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="glass-panel-dark p-4 rounded-2xl flex flex-col justify-center relative overflow-hidden">
                <div className="absolute top-0 right-0 p-2 opacity-10"><div className="w-12 h-12 rounded-full border-4 border-cyan-400"></div></div>
                <div className="text-[10px] text-cyan-400 font-bold uppercase tracking-widest mb-1">今日发电预估</div>
                <div className="text-xl font-bold text-white">{totalGenKwh} <span className="text-xs text-slate-500">kWh</span></div>
              </div>
              <div className="glass-panel-dark p-4 rounded-2xl flex flex-col justify-center relative overflow-hidden">
                <div className="absolute bottom-0 right-0 p-2 opacity-10"><div className="w-12 h-12 border-b-4 border-r-4 border-emerald-400 rounded-br-xl"></div></div>
                <div className="text-[10px] text-emerald-400 font-bold uppercase tracking-widest mb-1">预期峰值功率</div>
                <div className="text-xl font-bold text-white">{peakPower} <span className="text-xs text-slate-500">W</span></div>
              </div>
            </div>

            {/* AI Insight Box */}
            <div className="flex-1 glass-panel-dark p-6 rounded-3xl border border-white/5 bg-gradient-to-b from-white/5 to-transparent flex flex-col">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_10px_currentColor] animate-pulse"></div>
                <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">AI 分析报告</span>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">
                基于当前气象数据，预计未来6小时光伏产出平稳。建议在{chartData.reduce((prev: any, curr: any) => (curr.solarPredicted || 0) > (prev.solarPredicted || 0) ? curr : prev).time}左右进行大功率电器使用以最大化自用率。
              </p>

              <div className="mt-auto pt-4 flex gap-2">
                <span className="px-2 py-1 rounded bg-white/5 text-[10px] text-slate-400 border border-white/5">多云转晴</span>
                <span className="px-2 py-1 rounded bg-white/5 text-[10px] text-slate-400 border border-white/5">温度适宜</span>
              </div>
            </div>
          </div>
        </div>
      );
    } else if (expandedChart === 'BATTERY') {
      chartTitle = '电池电量历史 (SOC)';
      color = '#10b981';
      ChartComponent = (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={expandedData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorBattExp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.4} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} unit=" %" domain={[0, 100]} />
            <Tooltip content={<CustomTooltip />} />
            <Area name="Charge Level" type="monotone" dataKey="battery" stroke={color} strokeWidth={3} fillOpacity={1} fill="url(#colorBattExp)" />
          </AreaChart>
        </ResponsiveContainer>
      );
    } else if (expandedChart === 'LOAD') {
      chartTitle = '家庭能耗统计';
      color = '#3b82f6';
      ChartComponent = (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={expandedData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorLoadExp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.4} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} unit={timeRange === 'DAY' ? ' kW' : ' kWh'} />
            <Tooltip content={<CustomTooltip />} />
            <Area name="Consumption" type="monotone" dataKey="consumption" stroke={color} strokeWidth={3} fillOpacity={1} fill="url(#colorLoadExp)" />
          </AreaChart>
        </ResponsiveContainer>
      );
    } else {
      chartTitle = '电网交互分析';
      color = '#a855f7';
      ChartComponent = (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={expandedData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} unit={timeRange === 'DAY' ? ' kW' : ' kWh'} />
            <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <Bar name="Net Grid" dataKey="grid" radius={[4, 4, 0, 0]}>
              {expandedData.map((entry: any, index: number) => (
                <Cell key={`cell-${index}`} fill={entry.grid > 0 ? '#ef4444' : '#a855f7'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      );
    }

    return (
      <div className="w-full h-full flex flex-col p-8">
        {/* Header */}
        <div className="flex justify-between items-start mb-8">
          <div>
            <h2 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
              {chartTitle}
              {expandedChart === 'SOLAR' && timeRange === 'DAY' && (
                <span className="text-amber-500 text-lg italic font-black tracking-widest" style={{ textShadow: '0 0 10px rgba(245, 158, 11, 0.5)' }}>
                  AI 预测
                </span>
              )}
            </h2>
            <p className="text-slate-400 mt-1">
              {expandedChart === 'SOLAR' ? "24小时光伏出力详细统计与预测分析。" : "详细统计与预测分析。"}
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* Time Range Selector: Hide if SOLAR (as it's fixed 24h forecast) */}
            {expandedChart !== 'SOLAR' && (
              <div className="flex bg-slate-800/50 rounded-xl p-1 border border-white/5">
                {(['DAY', 'WEEK', 'MONTH'] as TimeRange[]).map((t) => (
                  <button
                    key={t}
                    onClick={(e) => { e.stopPropagation(); setTimeRange(t); }}
                    className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${timeRange === t
                      ? 'bg-slate-700 text-white shadow-lg'
                      : 'text-slate-500 hover:text-slate-300'
                      }`}
                  >
                    {t === 'DAY' ? '日' : t === 'WEEK' ? '周' : '月'}
                  </button>
                ))}
              </div>
            )}

            <button
              onClick={closeExpanded}
              className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white transition-colors"
            >
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Main Chart Area */}
        <div className="flex-1 w-full bg-slate-900/30 rounded-3xl border border-white/5 p-4 shadow-inner">
          {ChartComponent}
        </div>
      </div>
    );
  };

  return (
    <>
      <div className="grid grid-cols-4 gap-4 h-full">

        {/* 1. PV Output */}
        <div
          onClick={() => setExpandedChart('SOLAR')}
          className="glass-panel-dark p-4 rounded-3xl w-full flex flex-col relative overflow-hidden group hover:border-amber-500/50 cursor-pointer transition-all hover:scale-[1.02]"
        >
          <div className="flex justify-between items-start mb-2 z-10">
            <div>
              <h3 className="text-sm font-bold text-amber-500 uppercase tracking-widest">光伏产出</h3>
              <div className="text-lg font-bold text-white mt-0.5">
                {pvForecast ? Math.max(...pvForecast.predictions).toFixed(1) : 3.8} <span className="text-xs text-gray-500">kW (峰值)</span>
              </div>
            </div>
            <Maximize2 size={14} className="text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div className="flex-1 w-[120%] -ml-[10%] -mb-4 opacity-70 group-hover:opacity-100 transition-opacity">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={powerData}>
                <defs>
                  <linearGradient id="colorSolar" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="solar" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorSolar)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 2. Battery SOC */}
        <div
          onClick={() => setExpandedChart('BATTERY')}
          className="glass-panel-dark p-4 rounded-3xl w-full flex flex-col relative overflow-hidden group hover:border-emerald-500/50 cursor-pointer transition-all hover:scale-[1.02]"
        >
          <div className="flex justify-between items-start mb-2 z-10">
            <div>
              <h3 className="text-sm font-bold text-emerald-500 uppercase tracking-widest">电池电量</h3>
              <div className="text-lg font-bold text-white mt-0.5">82 <span className="text-xs text-gray-500">%</span></div>
            </div>
            <Maximize2 size={14} className="text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div className="flex-1 w-[120%] -ml-[10%] -mb-4 opacity-70 group-hover:opacity-100 transition-opacity">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={powerData}>
                <defs>
                  <linearGradient id="colorBattery" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="battery" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorBattery)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 3. Load Profile */}
        <div
          onClick={() => setExpandedChart('LOAD')}
          className="glass-panel-dark p-4 rounded-3xl w-full flex flex-col relative overflow-hidden group hover:border-blue-500/50 cursor-pointer transition-all hover:scale-[1.02]"
        >
          <div className="flex justify-between items-start mb-2 z-10">
            <div>
              <h3 className="text-sm font-bold text-blue-500 uppercase tracking-widest">家庭能耗</h3>
              <div className="text-lg font-bold text-white mt-0.5">1.3 <span className="text-xs text-gray-500">kW</span></div>
            </div>
            <Maximize2 size={14} className="text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div className="flex-1 w-[120%] -ml-[10%] -mb-4 opacity-70 group-hover:opacity-100 transition-opacity">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={powerData}>
                <defs>
                  <linearGradient id="colorLoad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="consumption" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorLoad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 4. Grid Interaction */}
        <div
          onClick={() => setExpandedChart('GRID')}
          className="glass-panel-dark p-4 rounded-3xl w-full flex flex-col relative overflow-hidden group hover:border-purple-500/50 cursor-pointer transition-all hover:scale-[1.02]"
        >
          <div className="flex justify-between items-start mb-2 z-10">
            <div>
              <h3 className="text-sm font-bold text-purple-500 uppercase tracking-widest">电网净值</h3>
              <div className="text-lg font-bold text-white mt-0.5">-0.5 <span className="text-xs text-gray-500">kW</span></div>
            </div>
            <Maximize2 size={14} className="text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div className="flex-1 w-[120%] -ml-[10%] -mb-4 opacity-70 group-hover:opacity-100 transition-opacity">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={powerData}>
                <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
                <Bar dataKey="grid" radius={[2, 2, 2, 2]}>
                  {powerData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.grid > 0 ? '#ef4444' : '#a855f7'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* EXPANDED OVERLAY */}
      {expandedChart && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-10 bg-slate-900/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-6xl h-[80vh] glass-panel-dark rounded-[3rem] shadow-2xl relative animate-in zoom-in-95 duration-300 border border-white/10 overflow-hidden">
            {renderExpandedContent()}
          </div>
        </div>
      )}
    </>
  );
};

export default ChartsPanel;
