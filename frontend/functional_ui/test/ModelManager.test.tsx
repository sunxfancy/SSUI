import React from 'react';
import { BlueprintProvider } from '@blueprintjs/core';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { ModelManager } from '../src/ui/models/ModelManager';
import { server } from './server';

const modelsUrl = 'http://localhost:7420/api/available_models';

function renderManager() {
  return render(
    <BlueprintProvider>
      <ModelManager path="" />
    </BlueprintProvider>,
  );
}

describe('ModelManager', () => {
  it('renders a deterministic empty state', async () => {
    server.use(http.get(modelsUrl, () => HttpResponse.json([])));
    renderManager();
    expect(await screen.findByText('No models found.')).toBeVisible();
    expect(screen.getByText('0 / 0')).toBeVisible();
  });

  it('renders API failures instead of an empty state', async () => {
    server.use(http.get(modelsUrl, () => new HttpResponse(null, { status: 500 })));
    renderManager();
    expect(await screen.findByText('Error: Failed to fetch models: 500')).toBeVisible();
  });

  it('renders returned model metadata', async () => {
    server.use(http.get(modelsUrl, () => HttpResponse.json([
      { name: 'Flux Schnell', path: '/models/flux.gguf', base_model: 'flux', tags: ['image'] },
    ])));
    renderManager();
    expect(await screen.findByText('Flux Schnell')).toBeVisible();
    expect(screen.getByText('/models/flux.gguf')).toBeVisible();
    expect(screen.getByText('image')).toBeVisible();
  });
});
