// Landing page animations

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

// Nothing is hidden in CSS, so if GSAP fails to load the page simply shows without animation
if (window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
    gsap.defaults({ ease: 'power2.out' });

    // 2. From seed to table: a 5 second timeline in four labelled steps.
    // Autoplays once when half the section is in view. Clicking a step stops
    // autoplay and plays that step from its label.
    function setupGrow() {
        const section = document.getElementById('grow');
        const list = section.querySelector('.step-list');
        const steps = [...list.querySelectorAll('.step')];
        const bars = steps.map((s) => s.querySelector('.step-bar'));
        const fill = list.querySelector('.connector-fill');
        const badges = steps.map((s) => s.querySelector('.step-badge'));
        const daysEl = document.getElementById('journal-days');
        const unitEl = daysEl.nextElementSibling;
        const noteEl = document.getElementById('journal-note');
        const harvestEl = document.getElementById('harvest-text');
        // Matches the day pills on the steps; harvest is on the Share day
        const stepDays = [1, 18, 30, 42];
        const notes = [
            'Seeds in · keep the soil damp',
            'Flowering · water again Thursday',
            'Rain on Friday · skip watering',
            'Ripe · ready to share',
        ];
        const stem = section.querySelector('.stem');
        const L = stem.getTotalLength();
        const labels = ['plant', 'log', 'care', 'share'];
        const starts = [0, 1.9, 3.0, 4.0, 5.0];
        const days = { n: 1 };
        let active = -1;

        // Stretch both lines from the bottom of the first badge to the top of the last one
        const fitLines = () => {
            const listTop = list.getBoundingClientRect().top;
            const start = badges[0].getBoundingClientRect().bottom - listTop;
            const end = badges[badges.length - 1].getBoundingClientRect().top - listTop;
            [list.querySelector('.connector'), fill].forEach((line) => {
                line.style.top = `${start}px`;
                line.style.height = `${end - start}px`;
            });
        };

        // Fill the connector down to the top of the active badge
        const fillTo = (i, instant) => {
            const length = badges[i].getBoundingClientRect().top - fill.getBoundingClientRect().top;
            const scaleY = Math.max(0, Math.min(1, length / fill.offsetHeight));
            gsap.to(fill, { scaleY, duration: instant ? 0 : 0.4 });
        };

        const showDay = (n) => {
            daysEl.textContent = n;
            unitEl.textContent = n === 1 ? 'DAY' : 'DAYS';
            const left = stepDays[3] - n;
            harvestEl.textContent = left > 0 ? `Harvest in ${left} days` : 'Ready to harvest';
        };

        const setActive = (i, instant) => {
            if (i === active) return;
            active = i;
            noteEl.textContent = notes[i];
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
                setActive(i, false);
                gsap.set(bars[i], { scaleX: Math.min(1, (t - starts[i]) / (starts[i + 1] - starts[i])) });
                showDay(Math.round(days.n));
            },
            onComplete: () => list.classList.remove('playing')
        });

        grow
            .addLabel('plant', starts[0])
            .fromTo('.stage', { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.5 }, 'plant')
            .fromTo('.harvest-chip', { opacity: 0, x: -8 }, { opacity: 1, x: 0, duration: 0.4 }, 'plant+=0.1')
            .fromTo(stem, { strokeDasharray: L, strokeDashoffset: L }, { strokeDashoffset: 0, duration: 1.2, ease: 'power2.inOut' }, 'plant+=0.3')
            .fromTo('.grow .leaf', { opacity: 0, scale: 0.96, svgOrigin: leafBase }, { opacity: 1, scale: 1, svgOrigin: leafBase, duration: 0.4, stagger: 0.12 }, 'plant+=0.6')

            .addLabel('log', starts[1])
            .fromTo('.journal-card', { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.4 }, 'log')
            .fromTo(days, { n: stepDays[0] }, { n: stepDays[1], duration: 0.9 }, 'log+=0.1')

            .addLabel('care', starts[2])
            .fromTo(days, { n: stepDays[1] }, { n: stepDays[2], duration: 0.7, immediateRender: false }, 'care+=0.1')
            .to('.grow .leaf-5, .grow .leaf-6', { rotation: -3, svgOrigin: leafBase, duration: 0.35, ease: 'sine.inOut', yoyo: true, repeat: 1, stagger: 0.1 }, 'care+=0.1')

            .addLabel('share', starts[3])
            .fromTo(days, { n: stepDays[2] }, { n: stepDays[3], duration: 0.7, immediateRender: false }, 'share+=0.1')
            .fromTo('.grow .fruit-stalk', { opacity: 0, scale: 0.96, svgOrigin: leafBase }, { opacity: 1, scale: 1, svgOrigin: leafBase, duration: 0.3 }, 'share')
            .fromTo('.grow .fruit', { opacity: 0, scale: 0.96, transformOrigin: '50% 50%' }, { opacity: 1, scale: 1, transformOrigin: '50% 50%', duration: 0.4, stagger: 0.15 }, 'share+=0.1')
            .fromTo('.grow .harvest-crate', { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.5 }, 'share+=0.2')
            .to({}, { duration: starts[4] - 4.8 }, 'share+=0.8');

        fitLines();
        grow.progress(0);
        setActive(0, true);
        showDay(stepDays[0]);
        const autoplay = ScrollTrigger.create({
            trigger: section, start: 'center bottom', once: true,
            onEnter: () => { list.classList.add('playing'); grow.play(0); }
        });

        const onClick = (e) => {
            const i = steps.indexOf(e.currentTarget);
            autoplay.kill();
            list.classList.remove('playing');
            grow.tweenFromTo(labels[i], starts[i + 1]);
        };
        steps.forEach((s) => s.addEventListener('click', onClick));

        // Fonts and window width can move the badges, so measure again
        const refit = () => { fitLines(); fillTo(active, true); };
        window.addEventListener('load', refit);
        window.addEventListener('resize', refit);

        return () => {
            steps.forEach((s) => s.removeEventListener('click', onClick));
            window.removeEventListener('load', refit);
            window.removeEventListener('resize', refit);
            list.classList.remove('playing');
        };
    }

    function landingMotion() {
        // 1. Sunrise, with the text starting right away instead of after the sky
        gsap.set('.hero .line', { clipPath: 'inset(0 0 100% 0)' });
        gsap.set('.hero .sub, .hero .ctas', { opacity: 0, y: 6 });
        gsap.set('.hero .glow', { opacity: 0 });
        gsap.set('.hero', { backgroundColor: '#FBEFD9' });
        gsap.set('.hero .sun', { y: '35vh' });
        gsap.set('#skyline .bld', { scaleY: 0.96, opacity: 0, transformOrigin: '50% 100%' });
        gsap.set('.cloud', { opacity: 0, x: -15 });

        gsap.timeline()
            .to('.hero .line', { clipPath: 'inset(0 0 0% 0)', duration: 0.45, stagger: 0.06 }, 0)
            .to('.hero .sub', { opacity: 1, y: 0, duration: 0.4 }, 0.1)
            .to('.hero .ctas', { opacity: 1, y: 0, duration: 0.4 }, 0.15)
            .to('.hero .sun', { y: 0, duration: 1.4 }, 0)
            .to('.hero .glow', { opacity: 1, duration: 1.4 }, 0.1)
            .to('.hero', { backgroundColor: '#E6F0DC', duration: 1.6, ease: 'power2.inOut' }, 0)
            .to('#skyline .bld', { scaleY: 1, opacity: 1, duration: 0.7, stagger: { each: 0.05, from: 'center' } }, 0.1)
            .to('.cloud', { opacity: 1, x: 0, duration: 0.8, stagger: 0.08 }, 0.3);

        [['.c1', 20, 26], ['.c2', -18, 34], ['.c3', 14, 20]].forEach(([sel, dx, dur]) =>
            gsap.to(sel, { x: dx, duration: dur, ease: 'none', repeat: -1, yoyo: true, delay: 2 })
        );

        // 2. From seed to table
        const cleanupGrow = setupGrow();

        // 3. Market row is handled by the wheel handler at the top

        // 4. Gardens parallax, half the data-speed distance
        document.querySelectorAll('.parallax').forEach((p) =>
            gsap.fromTo(p, { y: -p.dataset.speed / 2 }, {
                y: p.dataset.speed / 2, ease: 'none',
                scrollTrigger: { trigger: p, start: 'top bottom', end: 'bottom top', scrub: true }
            })
        );

        // 5. Choose a role, tiles rise once as soon as the section shows
        gsap.from('.tile', {
            y: 10, opacity: 0, duration: 0.45, stagger: 0.06,
            scrollTrigger: { trigger: '#dusk', start: 'top 90%', once: true }
        });

        return cleanupGrow;
    }

    // Runs for every screen size and every reduced-motion setting
    const mm = gsap.matchMedia();

    mm.add('(min-width: 0px)', () => {
        try {
            return landingMotion();
        } catch (error) {
            // Undo every set() so nothing stays hidden if setup breaks partway
            setTimeout(() => mm.revert());
        }
    });

    // 7. Filter chips: fade the new cards in and go back to the start of the row
    document.body.addEventListener('htmx:afterSwap', (e) => {
        if (e.detail.target.id !== 'track') return;
        row.scrollLeft = 0;
        gsap.fromTo('#track .card', { opacity: 0.35 }, { opacity: 1, duration: 0.18, ease: 'none' });
    });

    window.addEventListener('load', () => ScrollTrigger.refresh());
}
