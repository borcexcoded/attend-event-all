import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Church Attendance System",
  description: "Face recognition based attendance tracking for your church",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <div className="flex min-h-screen bg-background">
          <Sidebar />
          <main className="flex-1 ml-0 md:ml-[260px] min-h-screen">
            <div className="max-w-[1200px] mx-auto px-6 py-10 md:px-10 md:py-12">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
