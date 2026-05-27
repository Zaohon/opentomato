import { format, addHours, startOfHour } from 'date-fns';

const API_PROXY_URL = '/api/eas/api/predict/pv_forecast_clone1';
const TOKEN = "YzVjYjczOTgxNGIzMDMxY2YwYzhiNzQzMTYwMGZjN2NmNjUzZDM2Yg==";

export interface PVForecastResponse {
    predict_date: string;
    predictions: number[];
    actuals: number[];
    times: string[];
    metrics: {
        MAE: number;
        MAPE: number;
        RMSE: number;
    };
}

export const fetchPVForecast = async (predictDate?: string): Promise<PVForecastResponse | null> => {
    // If no date is provided, default to current time or a specific test time if needed.
    // For now, let's use a dynamic date based on user requirement or default to now.
    // User example used "2025-09-15 18:00:00".
    // We should probably use the current real time or allow passing it.

    const dateToUse = predictDate || format(new Date(), 'yyyy-MM-dd HH:mm:ss');

    try {
        const response = await fetch(API_PROXY_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': TOKEN
            },
            body: JSON.stringify({
                predict_date: dateToUse
            })
        });

        if (response.ok) {
            const data = await response.json();
            return data;
        } else {
            console.error('Failed to fetch PV forecast:', response.statusText);
            return null;
        }
    } catch (error) {
        console.error('Error fetching PV forecast:', error);
        return null;
    }
};
