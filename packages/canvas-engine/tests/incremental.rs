use ssui_canvas_engine::{Scene, SceneUpdate};
#[test]
fn incremental_updates_preserve_geometry_and_reject_invalid_projection() {
    let initial:Scene=serde_json::from_str(r#"{"layers":[{"id":"ink","visible":true,"opacity":1,"objects":[{"kind":"stroke","stroke":{"id":"s","width":5,"color":[1,0,0,1],"points":[{"x":1,"y":2,"pressure":1}]}}]}]}"#).unwrap();
    let update: SceneUpdate =
        serde_json::from_str(r#"{"layers":[{"id":"ink","visible":false,"opacity":0.5}]}"#).unwrap();
    let next = update.apply(&initial).unwrap();
    assert!(!next.layers[0].visible);
    assert_eq!(next.layers[0].opacity, 0.5);
    assert_eq!(
        serde_json::to_string(&next.layers[0].objects).unwrap(),
        serde_json::to_string(&initial.layers[0].objects).unwrap()
    );
    let invalid: SceneUpdate =
        serde_json::from_str(r#"{"layers":[{"id":"unknown","visible":true,"opacity":1}]}"#)
            .unwrap();
    assert!(invalid.apply(&initial).is_err());
    assert_eq!(initial.layers[0].opacity, 1.0);
    let duplicate:SceneUpdate=serde_json::from_str(r#"{"layers":[{"id":"ink","visible":true,"opacity":1},{"id":"ink","visible":true,"opacity":1}]}"#).unwrap();
    assert!(duplicate.apply(&initial).is_err());
}
