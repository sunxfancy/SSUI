// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from 'vscode';
import { Utils } from "vscode-uri";

function config() {
	return vscode.workspace.getConfiguration("ssui-vscode");
}

function createPreviewPanel(
    uri: vscode.Uri | undefined,
    displayColumn: vscode.ViewColumn | {
        viewColumn: vscode.ViewColumn;
        preserveFocus?: boolean | undefined;
    },
    title: string | undefined,
  ) {
    const previewTitle = title || `Preview: '${uri ? Utils.basename(uri) : "Unnamed"}'`;
	const URL = "http://localhost:7420/?path="+ uri?.fsPath;
	console.log("url: ", URL);
    const webViewPanel = vscode.window.createWebviewPanel("ssui-functional-ui", previewTitle, displayColumn, {
      enableFindWidget: false,
      enableScripts: true,
      retainContextWhenHidden: true,
    });
	webViewPanel.webview.html =  `<!DOCTYPE html>
            <html lang="en"">
            <head>
                <meta charset="UTF-8">
                <title>Preview</title>
                <style>
                    html { width: 100%; height: 100%; min-height: 100%; display: flex; }
                    body { flex: 1; display: flex; }
                    iframe { flex: 1; border: none; background: white; }
                </style>
            </head>
            <body>
                <iframe src="${URL}"></iframe>
            </body>
            </html>`;

    return webViewPanel;
  }


// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {

	// Use the console to output diagnostic information (console.log) and errors (console.error)
	// This line of code will only be executed once when your extension is activated
	console.log('Congratulations, your extension "ssui-vscode" is now active!');

	// The command has been defined in the package.json file
	// Now provide the implementation of the command with registerCommand
	// The commandId parameter must match the command field in package.json
	const disposable = vscode.commands.registerCommand('ssui-vscode.functional-ui', (a) => {
		// The code you place here will be executed every time your command is executed
		// Display a message box to the user
		const args = a || {};
		const options: {
			document?: vscode.TextDocument,
			uri?: vscode.Uri,
			content?: string,
			// eslint-disable-next-line no-unused-vars
			allowMultiplePanels?: boolean,
			title?: string,
			search?: any,
			displayColumn: vscode.ViewColumn | {
				viewColumn: vscode.ViewColumn;
				preserveFocus?: boolean | undefined;
			}
		} = {
			document: args.document,
			uri: args.uri,
			content: args.content,
			allowMultiplePanels: args.allowMultiplePanels,
			title: args.title,
			search: args.search,
			displayColumn: args.displayColumn || {
				viewColumn: vscode.ViewColumn.Beside,
				preserveFocus: config().get("preserveFocus"),
			},
		};

		if (!options.content
			&& !options.document
			&& !options.uri
			&& vscode.window.activeTextEditor?.document) {
			options.document = vscode.window.activeTextEditor.document;
		}
		if (!options.uri && options.document) {
			options.uri = options.document.uri;
		  }

		context.subscriptions.push( createPreviewPanel(options.uri, options.displayColumn, options.title));
	});

	context.subscriptions.push(disposable);
}

// This method is called when your extension is deactivated
export function deactivate() { }
