"use client";

import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { ChevronDown, Folder, Plus, Trash2 } from "lucide-react";
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
                // Select first project if none selected
                if (!currentProjectId && data.length > 0) {
                    setCurrentProject(data[0].project_id);
                }
            }
        } catch (error) {
            console.error("Failed to fetch projects:", error);
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
        <div className="relative mb-4 px-2">
            <div
                className="flex items-center justify-between p-2 rounded-lg bg-glass-100 hover:bg-glass-200 cursor-pointer transition-colors border border-transparent hover:border-cyber-blue/30"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-2 overflow-hidden">
                    <Folder className="w-4 h-4 text-cyber-blue shrink-0" />
                    <span className="text-sm font-medium theme-text-primary truncate">
                        {currentProject?.name || "Select Project"}
                    </span>
                </div>
                <ChevronDown className={`w-4 h-4 theme-text-muted transition-transform ${isOpen ? "rotate-180" : ""}`} />
            </div>

            {isOpen && (
                <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-gray-900 border border-glass rounded-lg shadow-xl backdrop-blur-xl overflow-hidden">
                    <div className="p-2 max-h-60 overflow-y-auto space-y-1">
                        {projects.map(project => (
                            <div
                                key={project.project_id}
                                className={`flex items-center justify-between p-2 rounded cursor-pointer text-sm ${currentProjectId === project.project_id
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
                                        try {
                                            const res = await fetch(`${API_BASE_URL}/api/v1/projects/${project.project_id}`, {
                                                method: "DELETE"
                                            });
                                            if (res.ok) {
                                                setProjects(projects.filter(p => p.project_id !== project.project_id));
                                                if (currentProjectId === project.project_id) {
                                                    setCurrentProject(null);
                                                }
                                            }
                                        } catch (err) {
                                            console.error("Failed to delete project:", err);
                                        }
                                    }}
                                    className="p-1 rounded opacity-50 hover:opacity-100 hover:bg-red-500/20 hover:text-red-400 transition-all"
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
