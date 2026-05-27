import React from 'react';
import { ComponentType, EnergyData } from '../types';

interface IsoHouseProps {
  onSelectComponent: (c: ComponentType) => void;
  data: EnergyData;
}

interface Point {
  x: number;
  y: number;
}

interface DeviceNode {
  id: ComponentType;
  x: number;
  y: number;
  label: string;
  short: string;
  color: string;
  value: string;
  unit: string;
  note?: string;
  subValue?: string;
  size?: number;
  panelWidth?: number;
  depth?: 'far' | 'mid' | 'near';
}

interface FlowLinkProps {
  id: string;
  from: Point;
  to: Point;
  color: string;
  active: boolean;
  reverse?: boolean;
  bend?: number;
}

const warmColors = {
  solar: '#c8a24f',
  grid: '#8a98aa',
  battery: '#53a98d',
  home: '#6f96c6',
  ev: '#8e88d0',
  hub: '#6f87b4',
  lineBase: '#d2ddeb',
};

const getCurvedPath = (from: Point, to: Point, bend = 0) => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.max(Math.hypot(dx, dy), 1);
  const nx = -dy / length;
  const ny = dx / length;

  const c1 = {
    x: from.x + dx * 0.32 + nx * bend,
    y: from.y + dy * 0.32 + ny * bend,
  };

  const c2 = {
    x: from.x + dx * 0.68 + nx * bend,
    y: from.y + dy * 0.68 + ny * bend,
  };

  return `M ${from.x} ${from.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${to.x} ${to.y}`;
};

const FlowLink: React.FC<FlowLinkProps> = ({ id, from, to, color, active, reverse = false, bend = 0 }) => {
  const path = getCurvedPath(from, to, bend);

  return (
    <g>
      <path d={path} fill="none" stroke={warmColors.lineBase} strokeWidth={6.2} strokeLinecap="round" strokeOpacity={active ? 0.52 : 0.22} />
      <path d={path} fill="none" stroke={color} strokeWidth={3.2} strokeLinecap="round" strokeOpacity={active ? 0.42 : 0.04} />

      {active ? (
        <>
          <path
            d={path}
            fill="none"
            stroke={color}
            strokeWidth={2.4}
            strokeLinecap="round"
            className="flow-path"
            strokeOpacity={0.88}
            style={{ animationDirection: reverse ? 'reverse' : 'normal' }}
          />

          <circle r={3.8} fill={color}>
            <animateMotion
              dur="2.5s"
              repeatCount="indefinite"
              path={path}
              keyPoints={reverse ? '1;0' : '0;1'}
              keyTimes="0;1"
              calcMode="linear"
            />
          </circle>

          <circle r={2.6} fill="#fffdf7" opacity={0.95}>
            <animateMotion
              dur="2.5s"
              begin="0.9s"
              repeatCount="indefinite"
              path={path}
              keyPoints={reverse ? '1;0' : '0;1'}
              keyTimes="0;1"
              calcMode="linear"
            />
          </circle>

          <path
            d={path}
            fill="none"
            stroke={color}
            strokeWidth={1.2}
            strokeOpacity={0.92}
            markerEnd={!reverse ? 'url(#flowArrow)' : undefined}
            markerStart={reverse ? 'url(#flowArrow)' : undefined}
          />
        </>
      ) : null}

      <circle cx={from.x} cy={from.y} r={3.6} fill={color} fillOpacity={active ? 0.78 : 0.22} />
      <circle cx={to.x} cy={to.y} r={3.6} fill={color} fillOpacity={active ? 0.78 : 0.22} />

      <title>{id}</title>
    </g>
  );
};

const DeviceBubble: React.FC<{ node: DeviceNode; onSelect: (c: ComponentType) => void }> = ({ node, onSelect }) => {
  const size = node.size || 56;
  const ring = size + 10;
  const panelWidth = node.panelWidth || 166;
  const panelHeight = node.subValue ? 90 : 72;
  const scale = node.depth === 'near' ? 1.08 : node.depth === 'far' ? 0.96 : 1.02;
  const pulseOpacity = node.depth === 'near' ? 0.16 : node.depth === 'far' ? 0.08 : 0.12;

  const handleKeyDown: React.KeyboardEventHandler<SVGGElement> = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(node.id);
    }
  };

  return (
    <g
      transform={`translate(${node.x},${node.y}) scale(${scale})`}
      onClick={() => onSelect(node.id)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`${node.label}，${node.value}${node.unit}`}
      className="cursor-pointer"
    >
      <circle r={ring} fill={node.color} opacity={pulseOpacity} className="pulse-soft" />
      <circle r={size} fill="rgba(250,253,255,0.95)" stroke={node.color} strokeWidth={2} />
      <circle r={size * 0.58} fill={node.color} opacity={0.16} />

      <text y={4} textAnchor="middle" fontSize={20} fontWeight={800} fill={node.color}>
        {node.short}
      </text>

      <rect
        x={-(panelWidth / 2)}
        y={size + 16}
        width={panelWidth}
        height={panelHeight}
        rx={16}
        fill="rgba(248,252,255,0.88)"
        stroke={node.color}
        strokeOpacity={0.25}
      />
      <text x={0} y={size + 41} textAnchor="middle" fontSize={14} fontWeight={700} fill="#6b7c90">
        {node.label}
      </text>
      <text x={0} y={size + 65} textAnchor="middle" fontSize={22} fontWeight={800} fill={node.color}>
        {node.value}
        <tspan dx={5} fontSize={13} fill="#7b8fa8">
          {node.unit}
        </tspan>
      </text>
      {node.subValue ? (
        <text x={0} y={size + 85} textAnchor="middle" fontSize={12} fontWeight={700} fill="#70829a">
          {node.subValue}
        </text>
      ) : null}

      {node.note ? (
        <text x={0} y={-size - 20} textAnchor="middle" fontSize={13} fontWeight={700} fill="#7b8ca2">
          {node.note}
        </text>
      ) : null}
    </g>
  );
};

const FLOW_EPSILON = 0.05;

const IsoHouse: React.FC<IsoHouseProps> = ({ onSelectComponent, data }) => {
  const hasFlow = (value: number) => Math.abs(value) > FLOW_EPSILON;

  const solarActive = hasFlow(data.solarPower);
  const gridActive = hasFlow(data.gridPower);
  const batteryActive = hasFlow(data.batteryPower);
  const homeActive = hasFlow(data.homeLoad);
  const evActive = hasFlow(data.evPower);

  const solarReverse = data.solarPower < -FLOW_EPSILON;
  const gridReverse = data.gridPower < -FLOW_EPSILON;
  const batteryReverse = data.batteryPower < -FLOW_EPSILON;
  const homeReverse = data.homeLoad < -FLOW_EPSILON;
  const evReverse = data.evPower < -FLOW_EPSILON;

  const nodes: Record<'solar' | 'grid' | 'battery' | 'ev' | 'home' | 'center', DeviceNode> = {
    solar: {
      id: ComponentType.SOLAR,
      x: 356,
      y: 214,
      label: '屋顶光伏',
      short: 'PV',
      color: warmColors.solar,
      value: data.solarPower.toFixed(2),
      unit: 'kW',
      note: '白天优先供给',
      size: 70,
      panelWidth: 186,
      depth: 'near',
    },
    grid: {
      id: ComponentType.GRID,
      x: 1008,
      y: 138,
      label: '公共电网',
      short: data.gridPower >= 0 ? 'IN' : 'OUT',
      color: warmColors.grid,
      value: Math.abs(data.gridPower).toFixed(2),
      unit: 'kW',
      note: gridActive ? (data.gridPower > 0 ? '购电中' : '回馈中') : '无交换',
      size: 58,
      panelWidth: 174,
      depth: 'far',
    },
    battery: {
      id: ComponentType.BATTERY,
      x: 300,
      y: 598,
      label: '家庭储能',
      short: 'BAT',
      color: warmColors.battery,
      value: data.batteryLevel.toFixed(0),
      unit: '%',
      note: batteryActive ? (data.batteryPower > 0 ? '正在充电' : '正在放电') : '待机',
      subValue: `功率 ${Math.abs(data.batteryPower).toFixed(2)} kW`,
      size: 70,
      panelWidth: 186,
      depth: 'near',
    },
    ev: {
      id: ComponentType.EV,
      x: 908,
      y: 606,
      label: '充电桩',
      short: 'EV',
      color: warmColors.ev,
      value: data.evPower.toFixed(2),
      unit: 'kW',
      note: evActive ? (data.evPower > 0 ? '补能中' : '反向供电') : '待机',
      size: 70,
      panelWidth: 186,
      depth: 'near',
    },
    home: {
      id: ComponentType.HOME,
      x: 996,
      y: 360,
      label: '家庭负载',
      short: 'HOME',
      color: warmColors.home,
      value: data.homeLoad.toFixed(2),
      unit: 'kW',
      size: 62,
      panelWidth: 178,
      depth: 'mid',
    },
    center: {
      id: ComponentType.INVERTER,
      x: 620,
      y: 390,
      label: '家庭能量中枢',
      short: 'EMS',
      color: warmColors.hub,
      value: data.revenue.toFixed(2),
      unit: '$',
      note: '智能调度中',
      size: 86,
      panelWidth: 204,
      depth: 'mid',
    },
  };

  const links: FlowLinkProps[] = [
    {
      id: 'solar->hub',
      from: { x: nodes.solar.x, y: nodes.solar.y },
      to: { x: nodes.center.x, y: nodes.center.y },
      color: warmColors.solar,
      active: solarActive,
      reverse: solarReverse,
      bend: -48,
    },
    {
      id: 'grid<->hub',
      from: { x: nodes.grid.x, y: nodes.grid.y },
      to: { x: nodes.center.x, y: nodes.center.y },
      color: warmColors.grid,
      active: gridActive,
      reverse: gridReverse,
      bend: 62,
    },
    {
      id: 'hub->home',
      from: { x: nodes.center.x, y: nodes.center.y },
      to: { x: nodes.home.x, y: nodes.home.y },
      color: warmColors.home,
      active: homeActive,
      reverse: homeReverse,
      bend: -10,
    },
    {
      id: 'hub->ev',
      from: { x: nodes.center.x, y: nodes.center.y },
      to: { x: nodes.ev.x, y: nodes.ev.y },
      color: warmColors.ev,
      active: evActive,
      reverse: evReverse,
      bend: 20,
    },
    {
      id: 'hub<->battery',
      from: { x: nodes.center.x, y: nodes.center.y },
      to: { x: nodes.battery.x, y: nodes.battery.y },
      color: warmColors.battery,
      active: batteryActive,
      reverse: batteryReverse,
      bend: -30,
    },
  ];

  const orderedNodes = [nodes.solar, nodes.grid, nodes.home, nodes.center, nodes.battery, nodes.ev];

  return (
    <div className="relative h-[458px] w-full overflow-hidden rounded-[24px] md:h-[562px]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_24%_18%,rgba(254,249,240,0.72),transparent_52%),radial-gradient(circle_at_82%_66%,rgba(210,227,245,0.58),transparent_58%),radial-gradient(circle_at_52%_52%,rgba(240,247,255,0.68),transparent_48%)]" />
      <div className="surface-noise absolute inset-0" />

      <svg viewBox="0 0 1260 780" className="relative h-full w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="hubGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#d6e6f8" stopOpacity="0.66" />
            <stop offset="100%" stopColor="#d6e6f8" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hubCore" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fbfdff" />
            <stop offset="100%" stopColor="#e4ecf6" />
          </radialGradient>
          <marker id="flowArrow" markerWidth="8" markerHeight="8" refX="5.5" refY="3.5" orient="auto-start-reverse">
            <path d="M 0 0 L 7 3.5 L 0 7 z" fill="context-stroke" />
          </marker>
        </defs>

        <circle cx={nodes.center.x} cy={nodes.center.y} r={220} fill="url(#hubGlow)" />
        <circle cx={nodes.center.x} cy={nodes.center.y} r={266} fill="none" stroke="rgba(150,168,191,0.32)" strokeWidth={2} strokeDasharray="10 10" />
        <circle cx={nodes.center.x} cy={nodes.center.y} r={114} fill="url(#hubCore)" opacity={0.84} />

        {links.map((link) => (
          <FlowLink key={link.id} {...link} />
        ))}

        {orderedNodes.map((node) => (
          <DeviceBubble key={node.id} node={node} onSelect={onSelectComponent} />
        ))}

      </svg>

      <div className="pointer-events-none absolute left-0 top-0 rounded-[20px] border border-[rgba(172,188,211,0.54)] bg-[rgba(248,252,255,0.84)] px-4 py-3">
        <div className="mb-3 text-base font-extrabold text-[#6d819d]">能量流向说明</div>
        <div className="flex items-center gap-2 text-[14px] font-semibold text-[#6c7e94]">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: warmColors.solar }} />
          光伏发电优先供家用
        </div>
        <div className="mt-2 flex items-center gap-2 text-[14px] font-semibold text-[#6c7e94]">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: warmColors.battery }} />
          储能自动充放电平衡
        </div>
        <div className="mt-2 flex items-center gap-2 text-[14px] font-semibold text-[#6c7e94]">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: warmColors.grid }} />
          峰谷时段智能买卖电
        </div>
      </div>
    </div>
  );
};

export default IsoHouse;
