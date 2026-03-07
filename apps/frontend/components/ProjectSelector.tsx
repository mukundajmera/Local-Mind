"use client";

import { useState, useEffect, useRef } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { ChevronDown, Folder, Plus, Trash2, AlertCircle } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface Project {
    project_id: string;
    name: string;
    description?: string;
    document_count: number;
}

export function ProjectSelector() {
    const { currentProjectId, setCurrentProject } = useWorkspaceStore();
    const [projects, setProjects] = useState<Project[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [showNewInput, setShowNewInput] = useState(false);
    const [newProjectName, setNewProjectName] = useState("");
    const [backendOffline, setBackendOffline] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        if (!isOpen) return;
        const handleClick = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, [isOpen]);

    // Fetch projects
    useEffect(() => {
        fetchProjects();
    }, []);

    const fetchProjects = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/projects`);
            if (res.ok) {
                const data = await res.json();
                setProjects(data);
                setBackendOffline(false);
                // Select first project if none selected
                if (!currentProjectId && data.length > 0) {
                    setCurrentProject(data[0].project_id);
                }
            }
        } catch {
            // Silently handle — backend may not be running yet
            setBackendOffline(true);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreateProject = async () => {
        if (!newProjectName.trim()) return;

        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/projects`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: newProjectName, description: "Created via UI" })
            });

            if (res.ok) {
                const newProject = await res.json();
                setProjects([...projects, newProject]);
                setCurrentProject(newProject.project_id);
                setNewProjectName("");
                setShowNewInput(false);
            }
        } catch (error) {
            console.error("Failed to create project:", error);
        }
    };

    const currentProject = projects.find(p => p.project_id === currentProjectId);

    return (
        <div className="relative mb-4 px-2" ref={dropdownRef}>
            <div
                className="flex items-center justify-between p-2 rounded-lg bg-glass-100 hover:bg-glass-200 cursor-pointer transition-colors border border-transparent hover:border-cyber-blue/30"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-2 overflow-hidden">
                    <Folder className="w-4 h-4 text-cyber-blue shrink-0" />
                    <span className="text-sm font-medium theme-text-primary truncate">
                        {isLoading ? "Loading..." : currentProject?.name || "Select Project"}
                    </span>
                    {backendOffline && (
                        <span title="Backend offline">
                            <AlertCircle className="w-3 h-3 text-orange-400 shrink-0" />
                        </span>
                    )}
                </div>
                <ChevronDown className={`w-4 h-4 theme-text-muted transition-transform shrink-0 ${isOpen ? "rotate-180" : ""}`} />
            </div>

            {isOpen && (
                <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-gray-900 border border-glass rounded-lg shadow-xl backdrop-blur-xl overflow-hidden">
                    <div className="p-2 max-h-60 overflow-y-auto space-y-1">
                        {projects.length === 0 && !isLoading && (
                            <p className="text-xs text-gray-500 text-center py-2">
                                {backendOffline ? "Backend offline" : "No projects yet"}
                            </p>
                        )}
                        {projects.map(project => (
                            <div
                                key={project.project_id}
                                className={`group flex items-center justify-between p-2 rounded cursor-pointer text-sm ${currentProjectId === project.project_id
                                    ? "bg-cyber-blue/20 text-cyber-blue"
                                    : "text-gray-300 hover:bg-white/5"
                                    }`}
                            >
                                <div
                                    className="flex-1 flex items-center gap-2 min-w-0"
                                    onClick={() => {
                                        setCurrentProject(project.project_id);
                                        setIsOpen(false);
                                    }}
                                >
                                    <span className="truncate">{project.name}</span>
                                    <span className="text-xs opacity-50">{project.document_count}</span>
                                </div>
                                <button
                                    onClick={async (e) => {
                                        e.stopPropagation();
                                        if (!confirm(`Delete project "${project.name}"? This cannot be undone.`)) return;

                                        // Optimistic update with rollback
                                        const prev = projects;
                                        setProjects(p => p.filter(x => x.project_id !== project.project_id));
                                        if (currentProjectId === project.project_id) {
                                            setCurrentProject(null);
                                        }

                                        try {
                                            const res = await fetch(`${API_BASE_URL}/api/v1/projects/${project.project_id}`, {
                                                method: "DELETE"
                                            });
                                            if (!res.ok) {
                                                // Rollback
                                                setProjects(prev);
                                            }
                                        } catch {
                                            // Rollback on network error
                                            setProjects(prev);
                                        }
                                    }}
                                    className="p-1 rounded opacity-0 group-hover:opacity-60 hover:!opacity-100 hover:bg-red-500/20 hover:text-red-400 transition-all"
                                    title="Delete project"
                                >
                                    <Trash2 className="w-3 h-3" />
                                </button>
                            </div>
                        ))}
                    </div>

                    <div className="border-t border-white/10 p-2">
                        {showNewInput ? (
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={newProjectName}
                                    onChange={(e) => setNewProjectName(e.target.value)}
                                    placeholder="Project Name"
                                    className="flex-1 bg-black/50 border border-white/20 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-cyber-blue"
                                    autoFocus
                                    onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                                />
                                <button
                                    onClick={handleCreateProject}
                                    className="text-xs bg-cyber-blue text-black px-2 rounded font-bold hover:bg-blue-400"
                                >
                                    OK
                                </button>
                            </div>
                        ) : (
                            <button
                                onClick={() => setShowNewInput(true)}
                                className="flex items-center gap-2 text-xs text-cyber-blue hover:text-white w-full p-1"
                            >
                                <Plus className="w-3 h-3" />
                                New Project
                            </button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
