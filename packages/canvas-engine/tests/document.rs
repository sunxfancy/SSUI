use ssui_canvas_engine::*;
fn fixture() -> Document {
    Document {
        version: 1,
        layers: vec![Layer {
            id: "layer".into(),
            name: "Ink".into(),
            visible: true,
            locked: false,
            opacity: 0.5,
            strokes: vec![Stroke {
                id: "stroke".into(),
                width: 10.0,
                color: [0.0, 0.0, 0.0, 1.0],
                points: vec![
                    Sample {
                        x: 0.0,
                        y: 0.0,
                        pressure: 0.2,
                    },
                    Sample {
                        x: 100.0,
                        y: 0.0,
                        pressure: 1.0,
                    },
                ],
            }],
        }],
    }
}
#[test]
fn delete_undo_redo_and_atomic_import() {
    let mut engine = Engine::new();
    engine
        .load_json(&serde_json::to_string(&fixture()).unwrap())
        .unwrap();
    let original = engine.export_json();
    assert!(engine.delete_stroke("stroke"));
    assert!(engine.hit_test(50.0, 0.0, 0.0).is_none());
    assert!(engine.undo());
    assert_eq!(engine.export_json(), original);
    assert!(engine.redo());
    assert!(engine.undo());
    assert!(engine.load_json(r#"{"version":2,"layers":[]}"#).is_err());
    assert_eq!(engine.export_json(), original);
}
#[test]
fn hit_pressure_visibility_and_locks() {
    let mut doc = fixture();
    assert!(doc.hit_test(0.0, 4.0, 0.0).is_none());
    assert_eq!(doc.hit_test(100.0, 4.0, 0.0).as_deref(), Some("stroke"));
    doc.layers[0].locked = true;
    assert!(doc.hit_test(50.0, 0.0, 0.0).is_none());
    let mut engine = Engine::new();
    engine
        .load_json(&serde_json::to_string(&doc).unwrap())
        .unwrap();
    assert!(!engine.delete_stroke("stroke"));
    doc.layers[0].locked = false;
    doc.layers[0].visible = false;
    assert!(doc.hit_test(50.0, 0.0, 0.0).is_none());
}
#[test]
fn correction_is_undoable_and_invalid_geometry_rejected() {
    let doc = fixture();
    let mut engine = Engine::new();
    engine
        .load_json(&serde_json::to_string(&doc).unwrap())
        .unwrap();
    let mut stroke = doc.layers[0].strokes[0].clone();
    stroke.points[1].y = 30.0;
    engine
        .replace_stroke("stroke", &serde_json::to_string(&stroke).unwrap())
        .unwrap();
    assert!(engine.hit_test(100.0, 30.0, 0.0).is_some());
    assert!(engine.undo());
    assert!(engine.hit_test(100.0, 0.0, 0.0).is_some());
    stroke.width = -1.0;
    assert!(engine
        .replace_stroke("stroke", &serde_json::to_string(&stroke).unwrap())
        .is_err());
}
#[test]
fn meshes_include_pressure_and_taps() {
    let mut stroke = fixture().layers.remove(0).strokes.remove(0);
    let mesh = tessellate(&stroke).unwrap();
    assert!(!mesh.indices.is_empty());
    assert!(mesh
        .indices
        .iter()
        .all(|i| (*i as usize) < mesh.vertices.len()));
    stroke.points.truncate(1);
    assert!(!tessellate(&stroke).unwrap().indices.is_empty());
}
