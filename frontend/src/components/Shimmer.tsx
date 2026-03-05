'use client';

import React from 'react';

interface ShimmerProps {
  className?: string;
}

// Base shimmer animation component
export const Shimmer: React.FC<ShimmerProps> = ({ className = '' }) => (
  <div 
    className={`animate-pulse bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200 bg-[length:200%_100%] rounded ${className}`}
    style={{
      animation: 'shimmer 1.5s ease-in-out infinite',
    }}
  />
);

// Card shimmer for dashboard cards
export const CardShimmer: React.FC = () => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <div className="flex items-center justify-between mb-4">
      <Shimmer className="h-4 w-24" />
      <Shimmer className="h-8 w-8 rounded-full" />
    </div>
    <Shimmer className="h-8 w-20 mb-2" />
    <Shimmer className="h-3 w-32" />
  </div>
);

// Stats card shimmer
export const StatsCardShimmer: React.FC = () => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <div className="flex items-center gap-4">
      <Shimmer className="h-12 w-12 rounded-lg" />
      <div className="flex-1">
        <Shimmer className="h-3 w-20 mb-2" />
        <Shimmer className="h-6 w-16" />
      </div>
    </div>
  </div>
);

// Table row shimmer
export const TableRowShimmer: React.FC = () => (
  <tr className="border-b border-gray-100">
    <td className="py-4 px-4">
      <div className="flex items-center gap-3">
        <Shimmer className="h-10 w-10 rounded-full" />
        <div>
          <Shimmer className="h-4 w-28 mb-1" />
          <Shimmer className="h-3 w-20" />
        </div>
      </div>
    </td>
    <td className="py-4 px-4"><Shimmer className="h-4 w-24" /></td>
    <td className="py-4 px-4"><Shimmer className="h-4 w-20" /></td>
    <td className="py-4 px-4"><Shimmer className="h-6 w-16 rounded-full" /></td>
    <td className="py-4 px-4"><Shimmer className="h-8 w-8 rounded" /></td>
  </tr>
);

// Table shimmer component
interface TableShimmerProps {
  rows?: number;
}

export const TableShimmer: React.FC<TableShimmerProps> = ({ rows = 5 }) => (
  <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
    <div className="p-4 border-b border-gray-100">
      <Shimmer className="h-6 w-40" />
    </div>
    <table className="w-full">
      <thead>
        <tr className="bg-gray-50">
          <th className="py-3 px-4 text-left"><Shimmer className="h-4 w-20" /></th>
          <th className="py-3 px-4 text-left"><Shimmer className="h-4 w-16" /></th>
          <th className="py-3 px-4 text-left"><Shimmer className="h-4 w-16" /></th>
          <th className="py-3 px-4 text-left"><Shimmer className="h-4 w-12" /></th>
          <th className="py-3 px-4 text-left"><Shimmer className="h-4 w-16" /></th>
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, i) => (
          <TableRowShimmer key={i} />
        ))}
      </tbody>
    </table>
  </div>
);

// Chart shimmer
export const ChartShimmer: React.FC<{ height?: string }> = ({ height = 'h-64' }) => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <div className="flex items-center justify-between mb-6">
      <Shimmer className="h-5 w-32" />
      <div className="flex gap-2">
        <Shimmer className="h-8 w-20 rounded" />
        <Shimmer className="h-8 w-20 rounded" />
      </div>
    </div>
    <div className={`${height} flex items-end gap-2`}>
      {Array.from({ length: 7 }).map((_, i) => (
        <Shimmer 
          key={i} 
          className="flex-1 rounded-t" 
          style={{ height: `${Math.random() * 60 + 40}%` } as React.CSSProperties}
        />
      ))}
    </div>
    <div className="flex justify-between mt-4">
      {Array.from({ length: 7 }).map((_, i) => (
        <Shimmer key={i} className="h-3 w-8" />
      ))}
    </div>
  </div>
);

// Line chart shimmer
export const LineChartShimmer: React.FC<{ height?: string }> = ({ height = 'h-64' }) => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <div className="flex items-center justify-between mb-6">
      <Shimmer className="h-5 w-40" />
      <Shimmer className="h-8 w-24 rounded" />
    </div>
    <div className={`${height} relative`}>
      {/* Y-axis labels */}
      <div className="absolute left-0 top-0 bottom-8 flex flex-col justify-between">
        {Array.from({ length: 5 }).map((_, i) => (
          <Shimmer key={i} className="h-3 w-6" />
        ))}
      </div>
      {/* Chart area */}
      <div className="ml-10 h-full flex items-center justify-center">
        <Shimmer className="w-full h-1/2 rounded" />
      </div>
    </div>
  </div>
);

// Member card shimmer
export const MemberCardShimmer: React.FC = () => (
  <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
    <div className="flex items-center gap-3 mb-3">
      <Shimmer className="h-12 w-12 rounded-full" />
      <div className="flex-1">
        <Shimmer className="h-4 w-24 mb-1" />
        <Shimmer className="h-3 w-16" />
      </div>
    </div>
    <div className="flex gap-2">
      <Shimmer className="h-6 w-16 rounded-full" />
      <Shimmer className="h-6 w-20 rounded-full" />
    </div>
  </div>
);

// Grid shimmer for member grid
export const MemberGridShimmer: React.FC<{ count?: number }> = ({ count = 8 }) => (
  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    {Array.from({ length: count }).map((_, i) => (
      <MemberCardShimmer key={i} />
    ))}
  </div>
);

// Analytics overview shimmer
export const AnalyticsOverviewShimmer: React.FC = () => (
  <div className="space-y-6">
    {/* Stats row */}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <StatsCardShimmer key={i} />
      ))}
    </div>
    
    {/* Charts row */}
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <ChartShimmer />
      <LineChartShimmer />
    </div>
    
    {/* Table */}
    <TableShimmer rows={5} />
  </div>
);

// Attendance list shimmer
export const AttendanceListShimmer: React.FC = () => (
  <div className="space-y-4">
    <div className="flex items-center justify-between">
      <Shimmer className="h-8 w-48" />
      <div className="flex gap-2">
        <Shimmer className="h-10 w-32 rounded-lg" />
        <Shimmer className="h-10 w-24 rounded-lg" />
      </div>
    </div>
    <TableShimmer rows={8} />
  </div>
);

// Meeting card shimmer
export const MeetingCardShimmer: React.FC = () => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <div className="flex items-start justify-between mb-4">
      <div className="flex-1">
        <Shimmer className="h-5 w-32 mb-2" />
        <Shimmer className="h-3 w-48" />
      </div>
      <Shimmer className="h-6 w-16 rounded-full" />
    </div>
    <div className="flex items-center gap-4 text-sm">
      <div className="flex items-center gap-1">
        <Shimmer className="h-4 w-4" />
        <Shimmer className="h-3 w-16" />
      </div>
      <div className="flex items-center gap-1">
        <Shimmer className="h-4 w-4" />
        <Shimmer className="h-3 w-20" />
      </div>
    </div>
  </div>
);

// Full page shimmer
export const PageShimmer: React.FC = () => (
  <div className="p-6 space-y-6">
    {/* Header */}
    <div className="flex items-center justify-between">
      <div>
        <Shimmer className="h-8 w-48 mb-2" />
        <Shimmer className="h-4 w-64" />
      </div>
      <Shimmer className="h-10 w-32 rounded-lg" />
    </div>
    
    {/* Content */}
    <AnalyticsOverviewShimmer />
  </div>
);

// Branch card shimmer
export const BranchCardShimmer: React.FC = () => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <div className="flex items-start gap-4">
      <Shimmer className="h-12 w-12 rounded-lg" />
      <div className="flex-1">
        <Shimmer className="h-5 w-32 mb-2" />
        <Shimmer className="h-3 w-48 mb-3" />
        <div className="flex gap-4">
          <div className="flex items-center gap-1">
            <Shimmer className="h-4 w-4" />
            <Shimmer className="h-3 w-20" />
          </div>
          <div className="flex items-center gap-1">
            <Shimmer className="h-4 w-4" />
            <Shimmer className="h-3 w-16" />
          </div>
        </div>
      </div>
    </div>
  </div>
);

// Branches grid shimmer
export const BranchesGridShimmer: React.FC<{ count?: number }> = ({ count = 6 }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {Array.from({ length: count }).map((_, i) => (
      <BranchCardShimmer key={i} />
    ))}
  </div>
);

// Add shimmer keyframes to global styles
export const ShimmerStyles = () => (
  <style jsx global>{`
    @keyframes shimmer {
      0% {
        background-position: 200% 0;
      }
      100% {
        background-position: -200% 0;
      }
    }
    
    .animate-shimmer {
      animation: shimmer 1.5s ease-in-out infinite;
      background: linear-gradient(
        90deg,
        #f0f0f0 25%,
        #e0e0e0 50%,
        #f0f0f0 75%
      );
      background-size: 200% 100%;
    }
  `}</style>
);

export default {
  Shimmer,
  CardShimmer,
  StatsCardShimmer,
  TableRowShimmer,
  TableShimmer,
  ChartShimmer,
  LineChartShimmer,
  MemberCardShimmer,
  MemberGridShimmer,
  AnalyticsOverviewShimmer,
  AttendanceListShimmer,
  MeetingCardShimmer,
  PageShimmer,
  BranchCardShimmer,
  BranchesGridShimmer,
  ShimmerStyles,
};
