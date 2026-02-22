/**
 * DatabaseTab Component
 * Educational Note: Attaches an account-level database connection to a project as a DATABASE source.
 */

import React, { useEffect, useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { CircleNotch, Plus } from '@phosphor-icons/react';
import { databasesAPI, type DatabaseConnection } from '@/lib/api/settings';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

interface DatabaseTabProps {
  isAtLimit: boolean;
  onAddDatabase: (connectionId: string, name?: string, description?: string) => Promise<void>;
}

export const DatabaseTab: React.FC<DatabaseTabProps> = ({ isAtLimit, onAddDatabase }) => {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const loadConnections = async () => {
    setLoading(true);
    try {
      const dbs = await databasesAPI.listDatabases();
      setConnections(dbs);
      if (!selectedConnectionId && dbs.length > 0) {
        setSelectedConnectionId(dbs[0].id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = connections.find((c) => c.id === selectedConnectionId);

  const handleAdd = async () => {
    if (!selectedConnectionId) return;
    setAdding(true);
    try {
      await onAddDatabase(
        selectedConnectionId,
        name.trim() || undefined,
        description.trim() || undefined
      );
      setName('');
      setDescription('');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="space-y-4">
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <CircleNotch size={28} className="animate-spin" />
        </div>
      ) : connections.length === 0 ? (
        <div className="space-y-2">
          <p className="text-sm">
            No database connections found.
          </p>
          <p className="text-xs text-muted-foreground">
            Add a connection in Admin Settings → Database Connections, then come back here to attach it to this project.
          </p>
          <Button variant="soft" onClick={loadConnections} disabled={loading}>
            Refresh
          </Button>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium block">Select connection</label>
            <Select
              value={selectedConnectionId}
              onValueChange={(v) => setSelectedConnectionId(v)}
              disabled={isAtLimit}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a database" />
              </SelectTrigger>
              <SelectContent>
                {connections.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name} ({c.db_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {selected ? (
              <p className="text-xs text-muted-foreground font-mono break-all">
                {selected.connection_uri_masked}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium block">Display name (optional)</label>
            <Input
              placeholder="Analytics DB"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isAtLimit || adding}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium block">Description (optional)</label>
            <Input
              placeholder="Read-only reporting database"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isAtLimit || adding}
            />
          </div>

          <div className="flex gap-2">
            <Button variant="soft" onClick={loadConnections} disabled={loading}>
              Refresh
            </Button>
            <Button
              onClick={handleAdd}
              disabled={isAtLimit || adding || !selectedConnectionId}
            >
              {adding ? (
                <>
                  <CircleNotch size={16} className="mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus size={16} className="mr-2" />
                  Add database source
                </>
              )}
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">
            NoobBook will capture a schema snapshot, generate a summary, and enable live SQL queries in chat.
          </p>
        </>
      )}
    </div>
  );
};

