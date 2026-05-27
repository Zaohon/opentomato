import React, { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';
import { TrendingUp, Zap, Calendar, X, DollarSign, Clock, Sparkles } from 'lucide-react';
import { TimeRange } from '../types';

// Mock Data Generator for Revenue Comparison
const generateRevenueData = (range: TimeRange) => {
  if (range === 'DAY') {
    // Hourly data for today
    return Array.from({ length: 12 }, (_, i) => {
      const hour = i * 2; // Every 2 hours
      const base = Math.random() * 2 + 0.5;
      const aiBoost = base * (1 + Math.random() * 0.3); // 0-30% boost
      return {
        time: `${hour}:00`,
        standard: +base.toFixed(2),
        ai: +aiBoost.toFixed(2),
      };
    });
  }
  
  if (range === 'MONTH') {
    // Daily data for last 15 days
    return Array.from({ length: 15 }, (_, i) => {
      const day = i + 1;
      const base = Math.random() * 10 + 5;
      const aiBoost = base * (1 + Math.random() * 0.25);
      return {
        time: `${day}日`,
        standard: +base.toFixed(2),
        ai: +aiBoost.toFixed(2),
      };
    });
  }

  // YEAR (Default fallback)
  const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
  return months.map(m => {
    const base = Math.random() * 200 + 100;
    const aiBoost = base * (1 + Math.random() * 0.2); // 20% boost
    return {
      time: m,
      standard: +base.toFixed(0),
      ai: +aiBoost.toFixed(0),
    };
  });
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="glass-panel-dark p-3 rounded-xl border border-white/10 text-xs z-[110] shadow-2xl backdrop-blur-3xl bg-slate-900/95">
        <p className="font-bold text-gray-200 mb-2 border-b border-white/10 pb-1">{label}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center justify-between gap-4 mb-1">
             <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.fill }}></div>
                <span className="text-gray-400 font-medium">{entry.name === 'ai' ? 'AI 优化' : '标准模式'}:</span>
             </div>
             <span className="text-white font-bold">${entry.value}</span>
          </div>
        ))}
        <div className="mt-2 pt-2 border-t border-white/5 flex justify-between">
           <span className="text-emerald-400 font-bold">增益:</span>
           <span className="text-emerald-400 font-bold">+${(payload[1].value - payload[0].value).toFixed(2)}</span>
        </div>
      </div>
    );
  }
  return null;
};

const RevenueCard: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>('MONTH');

  const data = useMemo(() => generateRevenueData(timeRange), [timeRange]);

  const totalRevenue = 1850.40;
  const aiGain = 240.50;
  const daysRunning = 145;

  // --- EXPANDED MODAL VIEW (Rendered via Portal) ---
  const expandedModal = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-900/80 backdrop-blur-sm animate-in fade-in duration-200">
       <div className="w-full max-w-6xl h-[85vh] glass-panel-dark rounded-[2.5rem] shadow-2xl relative animate-in zoom-in-95 duration-300 border border-white/10 overflow-hidden flex flex-col p-8">
          
          {/* Header */}
          <div className="flex justify-between items-start mb-6">
            <div>
               <h2 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
                  收益分析
                  <span className="px-3 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs font-bold border border-emerald-500/20 flex items-center gap-2">
                     <Sparkles size={14} /> AI 增强
                  </span>
               </h2>
               <p className="text-slate-400 mt-1">标准逻辑与 FeSolar AI 优化的对比分析。</p>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex bg-slate-800/50 rounded-xl p-1 border border-white/5">
                {(['DAY', 'MONTH', 'YEAR'] as TimeRange[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTimeRange(t)}
                    className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${
                      timeRange === t 
                      ? 'bg-slate-700 text-white shadow-lg' 
                      : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {t === 'DAY' ? '今日' : t === 'MONTH' ? '本月' : '本年'}
                  </button>
                ))}
              </div>
              <button 
                onClick={() => setIsExpanded(false)}
                className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white transition-colors"
              >
                <X size={24} />
              </button>
            </div>
          </div>

          {/* Chart Content */}
          <div className="flex-1 w-full bg-slate-900/30 rounded-3xl border border-white/5 p-6 shadow-inner relative">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} barGap={4}>
                   <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                   <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} dy={10} />
                   <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} unit="$" />
                   <Tooltip content={<CustomTooltip />} cursor={{fill: 'rgba(255,255,255,0.05)'}} />
                   <Legend 
                      verticalAlign="top" 
                      height={36} 
                      iconType="circle"
                      wrapperStyle={{ color: '#94a3b8', fontSize: '12px', fontWeight: 600 }} 
                      formatter={(value) => value === 'ai' ? 'AI 优化' : '标准模式'}
                   />
                   
                   <Bar name="standard" dataKey="standard" fill="#64748b" radius={[4, 4, 0, 0]} maxBarSize={50} />
                   
                   <Bar name="ai" dataKey="ai" fill="url(#colorAi)" radius={[4, 4, 0, 0]} maxBarSize={50}>
                       {/* Add gradient defs locally if needed, or rely on global defs */}
                   </Bar>
                </BarChart>
              </ResponsiveContainer>
              
              {/* Local Defs for Gradient */}
              <svg style={{ height: 0 }}>
                <defs>
                  <linearGradient id="colorAi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#34d399" stopOpacity={1} />
                    <stop offset="100%" stopColor="#059669" stopOpacity={1} />
                  </linearGradient>
                </defs>
              </svg>
          </div>

          {/* Summary Footer */}
          <div className="mt-6 grid grid-cols-3 gap-6">
             <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                <div className="text-xs text-slate-500 uppercase font-bold">总收益</div>
                <div className="text-2xl font-bold text-white mt-1">$12,450</div>
             </div>
             <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 relative overflow-hidden">
                <div className="relative z-10">
                  <div className="text-xs text-emerald-500/70 uppercase font-bold">AI 贡献</div>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">+$1,840</div>
                </div>
                <Sparkles className="absolute -bottom-2 -right-2 text-emerald-500/20 w-16 h-16" />
             </div>
             <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                <div className="text-xs text-slate-500 uppercase font-bold">性能提升</div>
                <div className="text-2xl font-bold text-white mt-1">14.8%</div>
             </div>
          </div>

       </div>
    </div>
  );

  if (isExpanded) {
    return (
      <>
        {/* Placeholder to keep layout shift minimal in sidebar */}
        <div className="h-28 w-full bg-transparent"></div>
        {/* Render Modal via Portal to break out of sidebar overflow/stacking context */}
        {createPortal(expandedModal, document.body)}
      </>
    );
  }

  // --- SIDEBAR SUMMARY CARD VIEW ---
  return (
    <div 
      onClick={() => setIsExpanded(true)}
      className="group w-full p-5 rounded-3xl bg-emerald-500/5 hover:bg-emerald-500/10 border border-emerald-500/20 hover:border-emerald-500/40 cursor-pointer transition-all duration-300 relative overflow-hidden"
    >
      <div className="flex justify-between items-start mb-4 relative z-10">
         <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-500 text-white shadow-lg shadow-emerald-500/30">
               <TrendingUp size={18} strokeWidth={3} />
            </div>
            <div>
               <div className="text-[10px] font-bold text-emerald-500/80 uppercase tracking-widest">累计收益</div>
               <div className="text-2xl font-bold text-white tracking-tight flex items-baseline gap-1">
                  ${totalRevenue.toLocaleString()} 
               </div>
            </div>
         </div>
      </div>

      <div className="relative z-10 grid grid-cols-2 gap-4 pt-3 border-t border-emerald-500/10">
         <div>
            <div className="text-[10px] text-slate-500 font-bold mb-0.5">AI 增益</div>
            <div className="text-sm font-bold text-emerald-400 flex items-center gap-1">
               +${aiGain.toFixed(2)}
               <Sparkles size={10} />
            </div>
         </div>
         <div className="text-right">
             <div className="text-[10px] text-slate-500 font-bold mb-0.5">运行时间</div>
             <div className="text-sm font-bold text-slate-300">{daysRunning} 天</div>
         </div>
      </div>

      {/* Background Decor */}
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl group-hover:bg-emerald-500/20 transition-colors"></div>
    </div>
  );
};

export default RevenueCard;