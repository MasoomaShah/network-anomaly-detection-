'use client';

import { AreaChart, Area, ResponsiveContainer } from 'recharts';

interface SparklineProps {
  data: number[];
  stroke?: string;
  height?: number;
}

export default function Sparkline({
  data,
  stroke = '#04D793',
  height = 32,
}: SparklineProps) {
  const chartData = data.map((value, index) => ({ index, value }));

  if (chartData.length < 2) {
    return <div style={{ height }} />;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={chartData} margin={{ top: 2, bottom: 2, left: 2, right: 2 }}>
        <defs>
          <linearGradient id="sparkGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.18} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={stroke}
          strokeWidth={1}
          fill="url(#sparkGradient)"
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
