use crate::Sample;
use serde::{Deserialize, Serialize};

/// Packed anchors: [x,y,inX,inY,outX,outY,normalized source arc parameter].
#[derive(Clone, Serialize, Deserialize)]
pub struct CurvePath {
    pub nodes: Vec<[f32; 7]>,
    pub pressure: Vec<[f32; 2]>,
    pub source_count: usize,
    pub tolerance: f32,
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> CurvePath {
        CurvePath {
            nodes: vec![
                [20., 64., 20., 64., 200., 64., 0.],
                [620., 64., 440., 64., 620., 64., 1.],
            ],
            pressure: vec![[0., 0.1], [0.5, 1.], [1., 0.1]],
            source_count: 1001,
            tolerance: 0.5,
        }
    }
    #[test]
    fn pressure_extrema_split_cubics_and_remain_in_mesh() {
        let c = fixture();
        c.validate().unwrap();
        assert_eq!(c.pressure_at(0.5), 1.);
        let stroke = crate::Stroke {
            id: "curve".into(),
            points: vec![],
            width: 40.,
            color: [0., 0., 1., 1.],
        };
        let mesh = crate::brush::mesh(&stroke, crate::Brush::Normal, 0., Some(&c)).unwrap();
        let max = mesh
            .vertices
            .iter()
            .map(|v| v.radius_feather[0])
            .fold(0f32, f32::max);
        let min = mesh
            .vertices
            .iter()
            .map(|v| v.radius_feather[0])
            .fold(f32::INFINITY, f32::min);
        assert!((max - 20.).abs() < 0.01);
        assert!((min - 2.).abs() < 0.01);
        assert!(c
            .flatten(0.2)
            .iter()
            .any(|p| (p.pressure - 1.).abs() < 0.001));
    }
    #[test]
    fn flatten_follows_bulges_and_rejects_malformed_pressure() {
        let mut c = fixture();
        c.nodes[0][5] = 464.;
        c.nodes[1][3] = 464.;
        assert!(c.flatten(0.1).iter().any(|p| p.y > 363.));
        c.pressure[1][0] = 0.;
        assert!(c.validate().is_err());
    }
}
impl CurvePath {
    pub fn validate(&self) -> Result<(), String> {
        if self.nodes.is_empty()
            || self.pressure.len() < 2
            || self.source_count == 0
            || !self.tolerance.is_finite()
            || self.tolerance <= 0.
            || self.nodes.iter().flatten().any(|v| !v.is_finite())
            || self.nodes[0][6] != 0.
            || (self.nodes.len() > 1 && self.nodes.last().unwrap()[6] != 1.)
            || self.nodes.windows(2).any(|w| w[0][6] >= w[1][6])
            || self.pressure.first().unwrap()[0] != 0.
            || self.pressure.last().unwrap()[0] != 1.
            || self
                .pressure
                .iter()
                .any(|p| !p[0].is_finite() || !p[1].is_finite() || !(0.0..=1.0).contains(&p[1]))
            || self.pressure.windows(2).any(|w| w[0][0] >= w[1][0])
        {
            return Err("Invalid Bezier geometry or pressure profile".into());
        }
        Ok(())
    }
    pub fn pressure_at(&self, t: f32) -> f32 {
        let i = self
            .pressure
            .partition_point(|p| p[0] <= t)
            .saturating_sub(1)
            .min(self.pressure.len() - 2);
        let a = self.pressure[i];
        let b = self.pressure[i + 1];
        a[1] + (b[1] - a[1]) * ((t - a[0]) / (b[0] - a[0])).clamp(0., 1.)
    }
    pub fn position(a: &[f32; 7], b: &[f32; 7], t: f32) -> [f32; 2] {
        let s = 1. - t;
        std::array::from_fn(|i| {
            s * s * s * a[i]
                + 3. * s * s * t * a[4 + i]
                + 3. * s * t * t * b[2 + i]
                + t * t * t * b[i]
        })
    }
    fn derivative(a: &[f32; 7], b: &[f32; 7], t: f32) -> [f32; 2] {
        let s = 1. - t;
        std::array::from_fn(|i| {
            3. * s * s * (a[4 + i] - a[i])
                + 6. * s * t * (b[2 + i] - a[4 + i])
                + 3. * t * t * (b[i] - b[2 + i])
        })
    }
    pub fn slice(a: &[f32; 7], b: &[f32; 7], lo: f32, hi: f32) -> [[f32; 2]; 4] {
        let p = Self::position(a, b, lo);
        let q = Self::position(a, b, hi);
        let dp = Self::derivative(a, b, lo);
        let dq = Self::derivative(a, b, hi);
        let d = (hi - lo) / 3.;
        [
            p,
            [p[0] + dp[0] * d, p[1] + dp[1] * d],
            [q[0] - dq[0] * d, q[1] - dq[1] * d],
            q,
        ]
    }
    pub fn cuts(&self, a: &[f32; 7], b: &[f32; 7]) -> Vec<f32> {
        let mut out = vec![0.];
        for p in &self.pressure {
            if p[0] > a[6] && p[0] < b[6] {
                out.push((p[0] - a[6]) / (b[6] - a[6]));
            }
        }
        out.push(1.);
        out
    }
    /// Temporary coverage/hit geometry, never the retained stroke representation.
    pub fn flatten(&self, tolerance: f32) -> Vec<Sample> {
        let n = self.nodes[0];
        let mut out = vec![Sample {
            x: n[0],
            y: n[1],
            pressure: self.pressure_at(0.),
        }];
        for w in self.nodes.windows(2) {
            let a = &w[0];
            let b = &w[1];
            let mut ts = self.cuts(a, b);
            let mut jobs = vec![(0f32, 1f32, 0)];
            while let Some((lo, hi, depth)) = jobs.pop() {
                let c = Self::slice(a, b, lo, hi);
                let d = [c[3][0] - c[0][0], c[3][1] - c[0][1]];
                let len = d[0].hypot(d[1]);
                let error = if len < 1e-6 {
                    (c[1][0] - c[0][0])
                        .hypot(c[1][1] - c[0][1])
                        .max((c[2][0] - c[0][0]).hypot(c[2][1] - c[0][1]))
                } else {
                    ((c[1][0] - c[0][0]) * d[1] - (c[1][1] - c[0][1]) * d[0])
                        .abs()
                        .max(((c[2][0] - c[0][0]) * d[1] - (c[2][1] - c[0][1]) * d[0]).abs())
                        / len
                };
                // The control polygon length catches collinear overshoot/backtracking.
                let polygon: f32 = c
                    .windows(2)
                    .map(|w| (w[1][0] - w[0][0]).hypot(w[1][1] - w[0][1]))
                    .sum();
                if (error > tolerance || polygon - len > tolerance) && depth < 16 {
                    let mid = (lo + hi) / 2.;
                    jobs.push((mid, hi, depth + 1));
                    jobs.push((lo, mid, depth + 1));
                } else {
                    ts.push(hi);
                }
            }
            ts.sort_by(f32::total_cmp);
            ts.dedup_by(|a, b| (*a - *b).abs() < 1e-7);
            for t in ts.into_iter().filter(|t| *t > 0.) {
                let p = Self::position(a, b, t);
                out.push(Sample {
                    x: p[0],
                    y: p[1],
                    pressure: self.pressure_at(a[6] + (b[6] - a[6]) * t),
                });
            }
        }
        out
    }
}
