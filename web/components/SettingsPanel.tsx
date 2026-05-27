import React from 'react';
import { ComponentType } from '../types';
import { X, Battery, Sun, Zap, Car, Home, Settings } from 'lucide-react';

interface SettingsPanelProps {
  component: ComponentType | null;
  onClose: () => void;
}

interface Tone {
  accent: string;
  soft: string;
  border: string;
}

const tones: Record<ComponentType, Tone> = {
  [ComponentType.SOLAR]: { accent: '#6f98c0', soft: 'rgba(111,152,192,0.14)', border: 'rgba(111,152,192,0.38)' },
  [ComponentType.BATTERY]: { accent: '#5ea58d', soft: 'rgba(94,165,141,0.14)', border: 'rgba(94,165,141,0.38)' },
  [ComponentType.EV]: { accent: '#8c99c1', soft: 'rgba(140,153,193,0.14)', border: 'rgba(140,153,193,0.38)' },
  [ComponentType.GRID]: { accent: '#8f9ba9', soft: 'rgba(143,155,169,0.14)', border: 'rgba(143,155,169,0.38)' },
  [ComponentType.HOME]: { accent: '#8a9db8', soft: 'rgba(138,157,184,0.14)', border: 'rgba(138,157,184,0.38)' },
  [ComponentType.INVERTER]: { accent: '#7d97bc', soft: 'rgba(125,151,188,0.14)', border: 'rgba(125,151,188,0.38)' },
};

const panelCardCls = 'glass-chip rounded-2xl border px-5 py-4';

const LabelRow: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="space-y-3">
    <label className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#7286a4]">{label}</label>
    {children}
  </div>
);

const SettingsPanel: React.FC<SettingsPanelProps> = ({ component, onClose }) => {
  if (!component) return null;

  const tone = tones[component];

  const renderContent = () => {
    switch (component) {
      case ComponentType.SOLAR:
        return (
          <div className="space-y-4">
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <LabelRow label="最大输出限制">
                <div className="flex items-center gap-4">
                  <input type="range" className="h-2 w-full cursor-pointer rounded-lg bg-[#dde8f5]" defaultValue={100} style={{ accentColor: tone.accent }} />
                  <span className="w-10 text-right text-sm font-bold text-[#607993]">100%</span>
                </div>
              </LabelRow>
            </div>
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <LabelRow label="MPPT 扫描间隔">
                <select className="w-full rounded-xl border border-[#c6d8eb] bg-white/84 px-4 py-2.5 text-sm text-[#5a7390] outline-none transition-colors focus:border-[#7694b9]">
                  <option>5 分钟</option>
                  <option>15 分钟</option>
                  <option>30 分钟</option>
                </select>
              </LabelRow>
            </div>
          </div>
        );

      case ComponentType.BATTERY:
        return (
          <div className="space-y-4">
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <LabelRow label="备电保留比例">
                <div className="flex items-center gap-4">
                  <input type="range" className="h-2 w-full cursor-pointer rounded-lg bg-[#dde8f5]" defaultValue={20} style={{ accentColor: tone.accent }} />
                  <span className="w-10 text-right text-sm font-bold text-[#607993]">20%</span>
                </div>
              </LabelRow>
            </div>
            <div className={`${panelCardCls} flex items-center justify-between`} style={{ borderColor: tone.border }}>
              <div>
                <span className="block font-bold text-[#4e657f]">网侧充电</span>
                <span className="text-xs text-[#768ba3]">夜间低价电时段自动充电</span>
              </div>
              <input type="checkbox" className="h-6 w-6 rounded-md border-none" style={{ accentColor: tone.accent }} />
            </div>
          </div>
        );

      case ComponentType.EV:
        return (
          <div className="space-y-4">
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <LabelRow label="充电速度">
                <div className="flex gap-3">
                  <button className="flex-1 rounded-xl py-2.5 text-sm font-bold text-white shadow-sm" style={{ background: tone.accent }}>
                    极速
                  </button>
                  <button className="flex-1 rounded-xl border border-[#c6d8eb] bg-white/12 py-2.5 text-sm font-bold text-[#607993] transition-colors hover:bg-white/42">
                    节能
                  </button>
                </div>
              </LabelRow>
            </div>
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <LabelRow label="目标续航">
                <div className="flex items-end gap-2">
                  <input
                    type="number"
                    defaultValue={80}
                    className="w-full border-b border-[#c3d5e8] bg-transparent text-3xl font-light text-[#4f6883] outline-none transition-colors focus:border-[#7694b9]"
                  />
                  <span className="mb-2 text-sm text-[#7a8fa8]">%</span>
                </div>
              </LabelRow>
            </div>
          </div>
        );

      case ComponentType.GRID:
        return (
          <div className="space-y-4">
            <div className={`${panelCardCls} flex items-center justify-between`} style={{ borderColor: tone.border }}>
              <div>
                <h4 className="font-bold text-[#4e657f]">并网售电</h4>
                <p className="mt-1 text-xs text-[#768ba3]">高价时段自动回馈电网</p>
              </div>
              <div className="h-6 w-12 rounded-full bg-[#dce8f5] p-1">
                <div className="h-4 w-4 translate-x-6 rounded-full bg-[#7a90ad] shadow-sm" />
              </div>
            </div>
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <LabelRow label="削峰填谷限制">
                <div className="flex items-end gap-2">
                  <input
                    type="number"
                    defaultValue={5.0}
                    className="w-full border-b border-[#c3d5e8] bg-transparent text-3xl font-light text-[#4f6883] outline-none transition-colors focus:border-[#7694b9]"
                  />
                  <span className="mb-2 text-sm text-[#7a8fa8]">kW</span>
                </div>
              </LabelRow>
            </div>
          </div>
        );

      case ComponentType.INVERTER:
        return (
          <div className="space-y-4">
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <div className="grid grid-cols-2 gap-6 text-center">
                <div>
                  <div className="text-3xl font-light text-[#4e657f]">
                    45<span className="text-lg">°C</span>
                  </div>
                  <div className="mt-1 text-[10px] font-bold uppercase tracking-wider text-[#7286a4]">温度</div>
                </div>
                <div>
                  <div className="text-3xl font-light text-[#5e9f88]">
                    98<span className="text-lg">%</span>
                  </div>
                  <div className="mt-1 text-[10px] font-bold uppercase tracking-wider text-[#7286a4]">效率</div>
                </div>
              </div>
            </div>
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <div className="text-sm leading-relaxed text-[#6c8098]">逆变器已匹配家庭负载优先策略，建议在傍晚提升储能充电下限以降低购电峰值。</div>
            </div>
          </div>
        );

      default:
        return (
          <div className="space-y-4">
            <div className={panelCardCls} style={{ borderColor: tone.border }}>
              <p className="mb-4 text-sm text-[#6f8197]">智能设备功耗监控。</p>
              <div className="space-y-3">
                <div className="rounded-xl border border-[#c7d8ea] bg-white/58 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-[#6f8197]">空调暖通</span>
                    <span className="font-bold text-[#4f6883]">2.1 kW</span>
                  </div>
                </div>
                <div className="rounded-xl border border-[#c7d8ea] bg-white/58 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-[#6f8197]">厨房电器</span>
                    <span className="font-bold text-[#4f6883]">0.8 kW</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
    }
  };

  const iconMap: Record<ComponentType, React.ElementType> = {
    [ComponentType.SOLAR]: Sun,
    [ComponentType.BATTERY]: Battery,
    [ComponentType.EV]: Car,
    [ComponentType.GRID]: Zap,
    [ComponentType.HOME]: Home,
    [ComponentType.INVERTER]: Settings,
  };

  const titleMap: Record<ComponentType, string> = {
    [ComponentType.SOLAR]: '光伏阵列',
    [ComponentType.BATTERY]: '储能电池',
    [ComponentType.EV]: '充电桩',
    [ComponentType.GRID]: '电网连接',
    [ComponentType.HOME]: '家庭负载',
    [ComponentType.INVERTER]: '五合一逆变器',
  };

  const Icon = iconMap[component];

  return (
    <div className="fixed inset-0 z-[130] flex justify-end bg-[rgba(70,88,112,0.3)] p-2 sm:p-3" onClick={onClose}>
      <div
        className="panel-enter glass-hero relative h-full w-full max-w-[430px] overflow-y-auto rounded-[30px] border border-[#c4d6ea]/72 p-6 shadow-[0_30px_70px_rgba(86,106,132,0.24)] backdrop-blur-xl sm:p-8"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="设备设置面板"
      >
        <button
          onClick={onClose}
          className="absolute right-7 top-7 rounded-full border border-[#c7d8ea] bg-white/62 p-2 text-[#7288a4] transition-colors hover:bg-[#eef5fc]"
          aria-label="关闭设置"
        >
          <X size={18} />
        </button>

        <div className="mb-6 mt-6 flex items-center gap-4">
          <div className="rounded-2xl border p-3" style={{ background: tone.soft, color: tone.accent, borderColor: tone.border }}>
            <Icon size={26} />
          </div>
          <div>
            <h3 className="font-heading text-2xl font-bold text-[#3f546e]">{titleMap[component]}</h3>
            <span className="inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest" style={{ background: tone.soft, color: tone.accent }}>
              Home Device Profile
            </span>
          </div>
        </div>

        {renderContent()}
      </div>
    </div>
  );
};

export default SettingsPanel;
