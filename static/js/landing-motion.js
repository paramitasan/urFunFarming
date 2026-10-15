// Landing page animations, see MOTION.md

// Market row: the mouse wheel scrolls it sideways while hovering,
// and hands back to the page once the row reaches either end
const row = document.getElementById('track-scroll');
row.addEventListener('wheel', (e) => {
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
    const max = row.scrollWidth - row.clientWidth;
    const atStart = row.scrollLeft <= 0 && e.deltaY < 0;
    const atEnd = row.scrollLeft >= max - 1 && e.deltaY > 0;
    if (max <= 0 || atStart || atEnd) return;
    e.preventDefault();
    row.scrollLeft += e.deltaY;
}, { passive: false });

if (!window.gsap || !window.ScrollTrigger) {
    // GSAP did not load, so show the hero without animation
    document.documentElement.classList.remove('motion');
} else {
    gsap.registerPlugin(ScrollTrigger);

    // 2. From seed to table: a 5 second timeline in four labelled steps.
    // Autoplays once when half the section is in view. Clicking a step stops
    // autoplay and plays that step from its label.
    function setupGrow(reduced) {
        const section = document.getElementById('grow');
        const list = section.querySelector('.step-list');
        const steps = [...list.querySelectorAll('.step')];
        const bars = steps.map((s) => s.querySelector('.step-bar'));
        const fill = list.querySelector('.connector-fill');
        const daysEl = document.getElementById('journal-days');
        const stem = section.querySelector('.stem');
        const L = stem.getTotalLength();
        const labels = ['plant', 'log', 'care', 'share'];
        const starts = [0, 1.9, 3.0, 4.0, 5.0];
        const days = { n: 1 };
        let active = -1;

        // Fill the connector down to the top of the active badge
        const fillTo = (i, instant) => {
            const badge = steps[i].querySelector('.step-badge');
            const length = badge.getBoundingClientRect().top - fill.getBoundingClientRect().top;
            const scaleY = Math.max(0, Math.min(1, length / fill.offsetHeight));
            gsap.to(fill, { scaleY, duration: instant ? 0 : 0.4, ease: 'power2.out' });
        };

        const setActive = (i, instant) => {
            if (i === active) return;
            active = i;
            steps.forEach((s, k) => {
                s.classList.toggle('on', k === i);
                if (k === i) s.setAttribute('aria-current', 'step');
                else s.removeAttribute('aria-current');
            });
            fillTo(i, instant);
        };

        const leafBase = (i, el) => el.dataset.base;

        const grow = gsap.timeline({
            paused: true,
            onUpdate: () => {
                const t = grow.time();
                let i = 0;
                while (i < 3 && t - 0.001 >= starts[i + 1]) i++;
                setActive(i, reduced);
                gsap.set(bars[i], { scaleX: Math.min(1, (t - starts[i]) / (starts[i + 1] - starts[i])) });
                daysEl.textContent = Math.round(days.n);
            },
            onComplete: () => list.classList.remove('playing')
        });

        grow
            .addLabel('plant', starts[0])
            .fromTo('.stage', { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.6, ease: 'power3.out' }, 'plant')
            .fromTo(stem, { strokeDasharray: L, strokeDashoffset: L }, { strokeDashoffset: 0, duration: 1.2, ease: 'power1.inOut' }, 'plant+=0.3')
            .fromTo('.grow .leaf', { scale: 0, svgOrigin: leafBase }, { scale: 1, svgOrigin: leafBase, duration: 0.45, ease: 'back.out(1.6)', stagger: 0.12 }, 'plant+=0.6')
            .fromTo('.harvest-chip', { opacity: 0, x: -16 }, { opacity: 1, x: 0, duration: 0.5, ease: 'power3.out' }, 'plant+=1.3')

            .addLabel('log', starts[1])
            .fromTo('.journal-card', { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }, 'log')
            .fromTo(days, { n: 1 }, { n: 18, duration: 0.9, ease: 'power1.out' }, 'log+=0.1')

            .addLabel('care', starts[2])
            .to('.grow .leaf-5, .grow .leaf-6', { rotation: -6, svgOrigin: leafBase, duration: 0.35, ease: 'sine.inOut', yoyo: true, repeat: 1, stagger: 0.1 }, 'care+=0.1')

            .addLabel('share', starts[3])
            .fromTo('.grow .fruit-stalk', { scale: 0, svgOrigin: leafBase }, { scale: 1, svgOrigin: leafBase, duration: 0.3, ease: 'power2.out' }, 'share')
            .fromTo('.grow .fruit', { scale: 0, transformOrigin: '50% 50%' }, { scale: 1, transformOrigin: '50% 50%', duration: 0.5, ease: 'back.out(1.7)', stagger: 0.15 }, 'share+=0.1')
            .fromTo('.grow .harvest-crate', { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.6, ease: 'power3.out' }, 'share+=0.2')
            .to({}, { duration: starts[4] - 4.8 }, 'share+=0.8');

        let autoplay = null;
        if (reduced) {
            grow.progress(1);
        } else {
            grow.progress(0);
            setActive(0, true);
            daysEl.textContent = '1';
            autoplay = ScrollTrigger.create({
                trigger: section, start: 'center bottom', once: true,
                onEnter: () => { list.classList.add('playing'); grow.play(0); }
            });
        }

        const onClick = (e) => {
            const i = steps.indexOf(e.currentTarget);
            if (autoplay) autoplay.kill();
            list.classList.remove('playing');
            if (reduced) grow.pause().seek(starts[i + 1], false);
            else grow.tweenFromTo(labels[i], starts[i + 1]);
        };
        steps.forEach((s) => s.addEventListener('click', onClick));

        // Fonts can shift the badges after first paint, so measure the fill again
        const refit = () => fillTo(active, true);
        window.addEventListener('load', refit);

        return () => {
            steps.forEach((s) => s.removeEventListener('click', onClick));
            window.removeEventListener('load', refit);
            list.classList.remove('playing');
        };
    }

    const mm = gsap.matchMedia();

    mm.add({ ok: '(prefers-reduced-motion: no-preference)', reduce: '(prefers-reduced-motion: reduce)' }, (ctx) => {
        // 8. Reduced motion: show the final states, no loops
        if (!ctx.conditions.ok) {
            gsap.set('.hero .line', { clipPath: 'inset(0 0 0% 0)' });
            gsap.set('.hero .sub, .hero .ctas, .hero .glow', { opacity: 1, y: 0 });
            return setupGrow(true);
        }

        // 1. Sunrise
        const dawn = gsap.timeline({ defaults: { ease: 'power3.out' } });
        dawn
            .set('.hero', { backgroundColor: '#FBEFD9' })
            .set('.hero .sun', { y: '70vh' })
            .set('#skyline .bld', { scaleY: 0.2, opacity: 0, transformOrigin: '50% 100%' })
            .set('.cloud', { opacity: 0, x: -30 })
            .to('.hero .sun', { y: 0, duration: 1.6, ease: 'power2.out' }, 0)
            .to('.hero .glow', { opacity: 1, duration: 1.6 }, 0.2)
            .to('.hero', { backgroundColor: '#E6F0DC', duration: 1.8, ease: 'power1.inOut' }, 0.1)
            .to('#skyline .bld', { scaleY: 1, opacity: 1, duration: 0.9, stagger: { each: 0.06, from: 'center' } }, 0.25)
            .to('.cloud', { opacity: 1, x: 0, duration: 1.0, stagger: 0.1 }, 0.6)
            .to('.hero .line', { clipPath: 'inset(0 0 0% 0)', duration: 0.7, stagger: 0.08 }, 0.5)
            .to('.hero .sub', { opacity: 1, y: 0, duration: 0.5 }, '-=0.3')
            .to('.hero .ctas', { opacity: 1, y: 0, duration: 0.5 }, '-=0.35');

        [['.c1', 40, 26], ['.c2', -36, 34], ['.c3', 28, 20]].forEach(([sel, dx, dur]) =>
            gsap.to(sel, { x: dx, duration: dur, ease: 'none', repeat: -1, yoyo: true, delay: 2 })
        );


        // 2. From seed to table
        const cleanupGrow = setupGrow(false);

        // 3. Market row is handled by the wheel handler at the top

        // 4. Gardens parallax
        document.querySelectorAll('.parallax').forEach((p) =>
            gsap.fromTo(p, { y: -p.dataset.speed * 1 }, {
                y: p.dataset.speed * 1, ease: 'none',
                scrollTrigger: { trigger: p, start: 'top bottom', end: 'bottom top', scrub: true }
            })
        );

        // 5. Choose a role, tiles slide up once
        gsap.from('.tile', {
            y: 24, opacity: 0, duration: 0.7, stagger: 0.1, ease: 'power3.out',
            scrollTrigger: { trigger: '#dusk', start: 'top 70%', once: true }
        });

        // 6. Magnetic buttons, mouse only
        if (matchMedia('(hover: hover) and (pointer: fine)').matches) {
            document.querySelectorAll('.magnetic').forEach((b) => {
                const xTo = gsap.quickTo(b, 'x', { duration: 0.4, ease: 'power3' });
                const yTo = gsap.quickTo(b, 'y', { duration: 0.4, ease: 'power3' });
                b.addEventListener('mousemove', (e) => {
                    const r = b.getBoundingClientRect();
                    xTo((e.clientX - (r.left + r.width / 2)) * 0.18);
                    yTo((e.clientY - (r.top + r.height / 2)) * 0.18);
                });
                b.addEventListener('mouseleave', () => { xTo(0); yTo(0); });
            });
        }


        return cleanupGrow;
    });

    // 7. Filter chips: fade the new cards in and go back to the start of the row
    document.body.addEventListener('htmx:afterSwap', (e) => {
        if (e.detail.target.id !== 'track') return;
        row.scrollLeft = 0;
        gsap.fromTo('#track .card', { opacity: 0.35 }, { opacity: 1, duration: 0.18, ease: 'none' });
    });

    window.addEventListener('load', () => ScrollTrigger.refresh());
}
