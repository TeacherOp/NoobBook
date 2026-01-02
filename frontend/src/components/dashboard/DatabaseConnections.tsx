import React, { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Trash, Database, Plus } from '@phosphor-icons/react';
import { useToast } from '../ui/toast';

interface DatabaseConnection {
  id: string;
  name: string;
  host: string;
  database: string;
}

interface DatabaseConnectionsProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DatabaseConnections: React.FC<DatabaseConnectionsProps> = ({
  isOpen,
  onClose,
}) => {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newConnection, setNewConnection] = useState({
    name: '',
    connection_string: '',
  });
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      loadConnections();
    }
  }, [isOpen]);

  const loadConnections = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/v1/database/connections?user_id=default_user');
      const data = await response.json();
      setConnections(data.connections || []);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load database connections',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const addConnection = async () => {
    if (!newConnection.name || !newConnection.connection_string) {
      toast({
        title: 'Error',
        description: 'Name and connection string are required',
        variant: 'destructive',
      });
      return;
    }

    try {
      const response = await fetch('/api/v1/database/connections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newConnection,
          user_id: 'default_user',
        }),
      });

      if (response.ok) {
        toast({
          title: 'Success',
          description: 'Database connection added successfully',
        });
        setNewConnection({ name: '', connection_string: '' });
        setShowAddForm(false);
        loadConnections();
      } else {
        const error = await response.json();
        toast({
          title: 'Error',
          description: error.error || 'Failed to add connection',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to add database connection',
        variant: 'destructive',
      });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Database size={20} />
            Database Connections
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Add Connection Form */}
          {showAddForm && (
            <div className="border rounded-lg p-4 space-y-3">
              <h3 className="font-medium">Add New Connection</h3>
              <div className="space-y-2">
                <Label htmlFor="db-name">Connection Name</Label>
                <Input
                  id="db-name"
                  placeholder="My Database"
                  value={newConnection.name}
                  onChange={(e) =>
                    setNewConnection({ ...newConnection, name: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="db-connection">Connection String</Label>
                <Input
                  id="db-connection"
                  type="password"
                  placeholder="postgresql://user:pass@host:5432/dbname"
                  value={newConnection.connection_string}
                  onChange={(e) =>
                    setNewConnection({
                      ...newConnection,
                      connection_string: e.target.value,
                    })
                  }
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={addConnection} size="sm">
                  Add Connection
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowAddForm(false)}
                  size="sm"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Add Button */}
          {!showAddForm && (
            <Button
              onClick={() => setShowAddForm(true)}
              variant="outline"
              className="w-full"
            >
              <Plus size={16} className="mr-2" />
              Add Database Connection
            </Button>
          )}

          {/* Connections List */}
          <div className="space-y-2">
            {isLoading ? (
              <div className="text-center py-4 text-muted-foreground">
                Loading connections...
              </div>
            ) : connections.length === 0 ? (
              <div className="text-center py-4 text-muted-foreground">
                No database connections configured
              </div>
            ) : (
              connections.map((conn) => (
                <div
                  key={conn.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div>
                    <div className="font-medium">{conn.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {conn.host} / {conn.database}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm">
                    <Trash size={16} />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
