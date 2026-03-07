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

    // Search and specific Edit states
    const [searchQuery, setSearchQuery] = useState("");
    const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
    const [editProjectName, setEditProjectName] = useState("");
    const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);

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

    const handleRenameStart = (e: React.MouseEvent, project: Project) => {
        e.stopPropagation();
        setEditingProjectId(project.project_id);
        setEditProjectName(project.name);
    };

    const handleRenameSave = async (projectId: string, e?: React.MouseEvent | React.KeyboardEvent) => {
        if (e) e.stopPropagation();
        if (!editProjectName.trim()) {
            setEditingProjectId(null);
            return;
        }

        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: editProjectName })
            });
            if (res.ok) {
                const updated = await res.json();
                setProjects(projects.map(p => p.project_id === projectId ? { ...p, name: updated.name } : p));
            }
        } catch (error) {
            console.error("Failed to rename project:", error);
        } finally {
            setEditingProjectId(null);
        }
    };

    const filteredProjects = projects.filter(p =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

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
                    {/* Search Bar */}
                    <div className="p-2 border-b border-white/10">
                        <input
                            type="text"
                            placeholder="Search projects..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                            className="w-full bg-black/50 border border-white/20 rounded px-2 py-1 flex-1 text-xs text-white focus:outline-none focus:border-cyber-blue"
                        />
                    </div>

                    <div className="p-2 max-h-60 overflow-y-auto space-y-1">
                        {filteredProjects.map(project => (
                            <div
                                key={project.project_id}
                                className={`flex items-center justify-between p-2 rounded cursor-pointer text-sm ${currentProjectId === project.project_id
                                    ? "bg-cyber-blue/20 text-cyber-blue"
                                    : "text-gray-300 hover:bg-white/5"
                                    }`}
                                onClick={() => {
                                    if (editingProjectId !== project.project_id) {
                                        setCurrentProject(project.project_id);
                                        setIsOpen(false);
                                        setSearchQuery("");
                                    }
                                }}
                            >
                                {editingProjectId === project.project_id ? (
                                    <div className="flex-1 flex items-center gap-2 min-w-0 mr-2">
                                        <input
                                            type="text"
                                            value={editProjectName}
                                            onChange={(e) => setEditProjectName(e.target.value)}
                                            onClick={(e) => e.stopPropagation()}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') handleRenameSave(project.project_id, e);
                                                if (e.key === 'Escape') setEditingProjectId(null);
                                            }}
                                            className="w-full bg-black/50 border border-white/20 rounded px-1 flex-1 text-xs text-white focus:outline-none focus:border-cyber-blue"
                                            autoFocus
                                        />
                                        <button onClick={(e) => handleRenameSave(project.project_id, e)} className="text-cyber-green hover:text-green-400">
                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                        </button>
                                        <button onClick={(e) => { e.stopPropagation(); setEditingProjectId(null); }} className="text-red-400 hover:text-red-300">
                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                        </button>
                                    </div>
                                ) : (
                                    <>
                                        {deletingProjectId === project.project_id ? (
                                            <div className="flex-1 flex items-center justify-between gap-2 min-w-0">
                                                <span className="text-xs text-red-400 truncate">Delete "{project.name}"?</span>
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={async (e) => {
                                                            e.stopPropagation();
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
                                                            } finally {
                                                                setDeletingProjectId(null);
                                                            }
                                                        }}
                                                        className="text-cyber-blue hover:text-white px-2 py-0.5 bg-red-900/30 rounded"
                                                    >
                                                        Yes
                                                    </button>
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); setDeletingProjectId(null); }}
                                                        className="text-gray-400 hover:text-white px-2 py-0.5 rounded"
                                                    >
                                                        No
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <>
                                                <div className="flex-1 flex items-center gap-2 min-w-0">
                                                    <span className="truncate">{project.name}</span>
                                                    <span className="text-xs opacity-50">{project.document_count}</span>
                                                </div>
                                                <div className="flex items-center gap-1 opacity-50 group-hover:opacity-100 hover:opacity-100">
                                                    <button
                                                        onClick={(e) => handleRenameStart(e, project)}
                                                        className="p-1 rounded hover:bg-cyber-blue/20 hover:text-cyber-blue transition-all"
                                                        title="Rename project"
                                                    >
                                                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                                        </svg>
                                                    </button>
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); setDeletingProjectId(project.project_id); }}
                                                        className="p-1 rounded hover:bg-red-500/20 hover:text-red-400 transition-all"
                                                        title="Delete project"
                                                    >
                                                        <Trash2 className="w-3 h-3" />
                                                    </button>
                                                </div>
                                            </>
                                        )}
                                    </>
                                )}
                            </div>
                        ))}
                        {filteredProjects.length === 0 && (
                            <div className="text-xs text-center text-gray-500 py-2">No projects found</div>
                        )}
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
