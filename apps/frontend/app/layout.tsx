import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "Sovereign Cognitive Engine",
    description: "Your personal AI research workspace with knowledge graphs and podcast synthesis",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="dark">
            <body className="mesh-gradient h-screen overflow-hidden antialiased">
                {/* Main workspace container */}
                <div className="h-full w-full p-4">
                    {children}
                </div>
            </body>
        </html>
    );
}
