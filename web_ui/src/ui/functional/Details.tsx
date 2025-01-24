import { useAsync } from "react-use";


type ScriptDetails = {
    [key: string]: any;
}

type DetailsProps = {
    path: string;
    selected: string;
};

export function DetailsPanel({ path, selected }: DetailsProps) {
    console.log('DetailsPanel', path, selected);
    async function queryDetails(): Promise<ScriptDetails> {
        console.log('queryDetails', path, selected);
        let response = await fetch('/api/prepare?' + new URLSearchParams({
            script_path: path,
            callable: selected,
        }), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                params: {}
            })
        });
        if (!response.ok) {
            throw new Error('Failed to fetch script details');
        }
        let data = await response.json() as ScriptDetails;
        console.log('Details', data);
        return data;
    }
    const state = useAsync(queryDetails);

    function render(value: ScriptDetails) {
        return <div>
            <h3>Details</h3>
            <pre>{JSON.stringify(value, null, 2)}</pre>
        </div>
    }

    return state.loading ? <p>Loading...</p> :
        state.error ? <p>Error: {state.error.message}</p> :
            render(state.value ?? {});
}