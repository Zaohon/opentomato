
export enum SystemMode {
  ECONOMIC = 'ECONOMIC',
  PROTECTION = 'PROTECTION',
  AI_FESOLAR = 'AI_FESOLAR',
}

export enum ComponentType {
  SOLAR = 'SOLAR',
  GRID = 'GRID',
  BATTERY = 'BATTERY',
  EV = 'EV',
  HOME = 'HOME',
  INVERTER = 'INVERTER',
}

export interface PVForecastMetric {
  MAE: number;
  MAPE: number;
  RMSE: number;
}

export interface PVForecastData {
  predict_date: string;
  predictions: number[];
  actuals: number[];
  times: string[];
  metrics: PVForecastMetric;
}

export type TimeRange = 'DAY' | 'WEEK' | 'MONTH' | 'YEAR';

export interface EnergyData {
  solarPower: number; // kW
  gridPower: number; // kW (+ import, - export)
  batteryPower: number; // kW (+ charge, - discharge)
  batteryLevel: number; // %
  evPower: number; // kW
  homeLoad: number; // kW
  revenue: number; // $
  timestamp: string;
}

export interface ChartDataPoint {
  time: string;
  solar: number | null;
  solarPredicted?: number | null; // For prediction curve
  consumption: number;
  battery: number;
  grid: number; // + Import, - Export
}

export interface RevenueDataPoint {
  day: string;
  amount: number;
}

export interface AIStatus {
  active: boolean;
  message: string;
  suggestion: string;
  loading: boolean;
}
