"use client";

import React, { useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { HourlyTrendPoint } from "@/types/observation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, Eye, BarChart2 } from "lucide-react";

interface HistoricalTrendChartProps {
  data: HourlyTrendPoint[];
  stationName: string;
}

export const HistoricalTrendChart: React.FC<HistoricalTrendChartProps> = ({
  data,
  stationName,
}) => {
  const [metric, setMetric] = useState<"aqi" | "pm2_5" | "pm10">("aqi");
  const [showTableView, setShowTableView] = useState(false);

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">24-Hour Historical Air Trend</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-slate-500">
            No historical hourly records currently logged for {stationName}.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Format chart data
  const chartData = data.map((d) => {
    const date = new Date(d.time);
    const hours = date.getHours().toString().padStart(2, "0");
    const minutes = date.getMinutes().toString().padStart(2, "0");
    return {
      time: `${hours}:${minutes}`,
      fullTime: date.toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }),
      aqi: d.aqi ?? 0,
      pm2_5: d.pm2_5 ?? 0,
      pm10: d.pm10 ?? 0,
      category: d.category || "Unknown",
    };
  });

  const metricConfig = {
    aqi: { label: "CPCB AQI Index", unit: "AQI", color: "#059669" },
    pm2_5: { label: "PM2.5 Concentration", unit: "µg/m³", color: "#d97706" },
    pm10: { label: "PM10 Concentration", unit: "µg/m³", color: "#ea580c" },
  };

  const currentMetric = metricConfig[metric];

  return (
    <Card className="shadow-sm">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between pb-2 gap-4">
        <div>
          <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            24-Hour Observation Trend — {stationName}
          </CardTitle>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Real hourly observations recorded by monitoring sensors.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Metric Selector Buttons */}
          <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-slate-50 dark:border-slate-800 dark:bg-slate-900" role="group" aria-label="Select Metric">
            <button
              onClick={() => setMetric("aqi")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                metric === "aqi"
                  ? "bg-white text-emerald-800 shadow-xs font-bold dark:bg-slate-800 dark:text-emerald-300"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-400"
              }`}
              aria-pressed={metric === "aqi"}
            >
              AQI
            </button>
            <button
              onClick={() => setMetric("pm2_5")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                metric === "pm2_5"
                  ? "bg-white text-emerald-800 shadow-xs font-bold dark:bg-slate-800 dark:text-emerald-300"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-400"
              }`}
              aria-pressed={metric === "pm2_5"}
            >
              PM2.5
            </button>
            <button
              onClick={() => setMetric("pm10")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                metric === "pm10"
                  ? "bg-white text-emerald-800 shadow-xs font-bold dark:bg-slate-800 dark:text-emerald-300"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-400"
              }`}
              aria-pressed={metric === "pm10"}
            >
              PM10
            </button>
          </div>

          {/* Accessible Table View Toggle */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowTableView(!showTableView)}
            className="flex items-center gap-1.5 text-xs"
            aria-label={showTableView ? "Show visual chart view" : "Show accessible data table view"}
          >
            {showTableView ? (
              <>
                <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Chart</span>
              </>
            ) : (
              <>
                <Table className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Table</span>
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {showTableView ? (
          /* Accessible HTML Table for Screen Readers */
          <div className="overflow-x-auto max-h-72">
            <table className="w-full text-left text-xs text-slate-600 dark:text-slate-400" aria-label={`Hourly air quality table for ${stationName}`}>
              <thead className="sticky top-0 bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                <tr>
                  <th scope="col" className="px-3 py-2">Time (IST)</th>
                  <th scope="col" className="px-3 py-2">AQI</th>
                  <th scope="col" className="px-3 py-2">PM2.5 (µg/m³)</th>
                  <th scope="col" className="px-3 py-2">PM10 (µg/m³)</th>
                  <th scope="col" className="px-3 py-2">CPCB Category</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {chartData.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-900/50">
                    <td className="px-3 py-2 font-medium text-slate-900 dark:text-slate-100">{row.fullTime}</td>
                    <td className="px-3 py-2 font-bold text-emerald-700 dark:text-emerald-400">{row.aqi}</td>
                    <td className="px-3 py-2">{row.pm2_5}</td>
                    <td className="px-3 py-2">{row.pm10}</td>
                    <td className="px-3 py-2">{row.category}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* Recharts Interactive Visual Area Chart */
          <div className="h-64 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="metricGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={currentMetric.color} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={currentMetric.color} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  tickLine={false}
                  axisLine={{ stroke: "#cbd5e1" }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload;
                      return (
                        <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-md text-xs space-y-1 dark:border-slate-700 dark:bg-slate-900">
                          <p className="font-bold text-slate-800 dark:text-slate-100">{item.fullTime}</p>
                          <p className="text-emerald-700 font-semibold dark:text-emerald-400">
                            {currentMetric.label}: {item[metric]} {currentMetric.unit}
                          </p>
                          <p className="text-slate-500">Category: {item.category}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey={metric}
                  stroke={currentMetric.color}
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#metricGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
