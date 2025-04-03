import React, { useEffect, useState } from 'react';
import { Spinner, Tabs, Tab } from '@blueprintjs/core';
import axios from 'axios';
import CivitaiModelCard from './CivitaiModelCard';
import { CivitaiModel } from '../types/civitai';

interface CivitaiModelsProps {
  onModelSelect?: (model: CivitaiModel) => void;
}

const CivitaiModels: React.FC<CivitaiModelsProps> = ({ onModelSelect }) => {
  const [models, setModels] = useState<CivitaiModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string>('all');

  useEffect(() => {
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      setLoading(true);
      const response = await axios.get('https://civitai.com/api/v1/models', {
        params: {
          limit: 50,
          sort: 'Newest'
        }
      });
      setModels(response.data.items);
      setError(null);
    } catch (err) {
      setError('获取模型列表失败');
      console.error('Error fetching models:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredModels = selectedType === 'all' 
    ? models 
    : models.filter(model => model.type === selectedType);

  const modelTypes = ['all', ...new Set(models.map(model => model.type))];

  return (
    <div style={{ padding: '20px' }}>
      <Tabs
        selectedTabId={selectedType}
        onChange={(newTabId) => setSelectedType(newTabId as string)}
      >
        {modelTypes.map(type => (
          <Tab 
            key={type} 
            id={type} 
            title={type === 'all' ? '全部' : type} 
          />
        ))}
      </Tabs>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Spinner />
        </div>
      ) : error ? (
        <div style={{ color: 'red', textAlign: 'center', padding: '20px' }}>
          {error}
        </div>
      ) : (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '20px',
          padding: '20px',
          maxHeight: 'calc(100vh - 100px)',
          overflow: 'auto'
        }}>
          {filteredModels.map(model => (
            <CivitaiModelCard 
              key={model.id}
              model={model}
              onModelSelect={onModelSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default CivitaiModels; 