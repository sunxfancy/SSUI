import React from 'react';

export interface IComponent<P = {}, S = {}> extends React.Component<P, S> {}
export class IComponent<P, S> extends React.Component<P, S> {
    onExecute(): any {}
}