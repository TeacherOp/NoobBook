import React, { useState } from 'react';
import { ProjectList } from '../project';
import { AppSettings } from './AppSettings';
import { DatabaseConnections } from './DatabaseConnections';
import { Button } from '../ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Gear, Ghost, Sparkle, GithubLogo, YoutubeLogo, BookOpen, Database } from '@phosphor-icons/react';
import { ToastContainer, useToast } from '../ui/toast';

/**
 * Dashboard Component
 * Educational Note: Main dashboard layout for the NotebookLM clone application.
 * This component manages the projects list and application settings.
 */

interface DashboardProps {
  onSelectProject: (project: any) => void;
  onCreateNewProject: () => void;
  refreshTrigger?: number;
}

export const Dashboard: React.FC<DashboardProps> = ({
  onSelectProject,
  onCreateNewProject,
  refreshTrigger = 0
}) => {
  const [appSettingsOpen, setAppSettingsOpen] = useState(false);
  const [databaseConnectionsOpen, setDatabaseConnectionsOpen] = useState(false);
  const { toasts, dismissToast } = useToast();

  return (
    <div className="min-h-screen bg-background">
      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Header - contained within same width as content */}
      <header className="h-14 bg-background">
        <div className="container mx-auto px-4 h-full flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ghost size={24} weight="fill" className="text-primary" />
            <h1 className="text-lg font-semibold">NoobBook</h1>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDatabaseConnectionsOpen(true)}
              className="gap-2"
            >
              <Database size={16} />
              Databases
            </Button>
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAppSettingsOpen(true)}
              className="gap-2"
            >
              <Gear size={16} />
              App Settings
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content - Two Part Layout */}
      <main className="container mx-auto px-4 py-6 flex flex-col h-[calc(100vh-56px)]">
        {/* Top Section: Projects (Scrollable) */}
        <div className="flex-1 min-h-0 overflow-y-auto mb-6">
          <ProjectList
            onSelectProject={onSelectProject}
            onCreateNew={onCreateNewProject}
            refreshTrigger={refreshTrigger}
          />
        </div>

        {/* Bottom Section: Learning Info Cards */}
        <div className="flex-shrink-0 grid grid-cols-1 md:grid-cols-2 gap-4 pb-4">
          {/* Card 1: Session 3 - What We're Building */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkle size={20} className="text-primary" />
                Session 3: The Complete AI Tool
              </CardTitle>
              <CardDescription>
                Build a production-ready AI application combining everything from the course into one powerful tool.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {['AI Chat', 'RAG', 'Image Gen', 'Video Gen', 'Realtime Transcription', 'Memories', 'Subagents', 'Deep Research', 'Web Search'].map((feature) => (
                  <Badge key={feature} variant="secondary" className="rounded-md">
                    {feature}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Previous Sessions & Resources */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpen size={20} className="text-primary" />
                Previous Sessions & Resources
              </CardTitle>
              <CardDescription>
                Catch up on the fundamentals from Sessions 1 & 2, and access all course materials on GitHub.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <a
                href="https://www.youtube.com/watch?v=jsdKgmU3DJA"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm hover:text-primary transition-colors"
              >
                <YoutubeLogo size={18} className="text-red-500" />
                <span>Session 1: API Basics, Parameters & Tool Use</span>
              </a>
              <a
                href="https://www.youtube.com/watch?v=RgykmlWXzns"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm hover:text-primary transition-colors"
              >
                <YoutubeLogo size={18} className="text-red-500" />
                <span>Session 2: Chat, Memory & AI Agents</span>
              </a>
              <a
                href="https://github.com/TeacherOp/growthx_1"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm hover:text-primary transition-colors"
              >
                <GithubLogo size={18} />
                <span>Course Code & Notes Repository</span>
              </a>
            </CardContent>
          </Card>
        </div>
      </main>

      {/* App Settings Dialog */}
      <AppSettings open={appSettingsOpen} onOpenChange={setAppSettingsOpen} />
      
      {/* Database Connections Dialog */}
      <DatabaseConnections 
        isOpen={databaseConnectionsOpen} 
        onClose={() => setDatabaseConnectionsOpen(false)} 
      />
    </div>
  );
};