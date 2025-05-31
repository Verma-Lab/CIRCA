import express from 'express';
import Razorpay from 'razorpay';
import crypto from 'crypto';
import firestore from '../services/db/firestore.js';
import jwt from 'jsonwebtoken';

const router = express.Router();

// Define plans with location-based pricing
const PLAN_PRICES = {
  india: {
    free: { price: 0 },
    pro: { price: 200000 }, // ₹2000.00 in paise
    business: { price: 'custom' }
  },
  usa: {
    free: { price: 0 },
    pro: { price: 3900 }, // $39.00 in cents
    business: { price: 'custom' }
  }
};

// Initialize Razorpay
const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID,
  key_secret: process.env.RAZORPAY_KEY_SECRET
});

// Authentication middleware
const authenticateToken = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
      return res.status(401).json({ error: 'Authentication token required' });
    }

    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = { userId: decoded.userId };
    next();
  } catch (error) {
    console.error('Authentication error:', error);
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
};

// Create order endpoint
router.post('/create-order', authenticateToken, async (req, res) => {
  const { plan, userLocation = 'usa' } = req.body;
  const location = userLocation.toLowerCase();

  // Validate location
  if (!PLAN_PRICES[location]) {
    return res.status(400).json({ error: 'Invalid location' });
  }

  // Validate plan
  if (!PLAN_PRICES[location][plan]) {
    return res.status(400).json({ error: 'Invalid plan selected' });
  }

  try {
    if (plan === 'free') {
      await firestore.db.collection('users').doc(req.user.userId).update({
        plan: 'free',
        limits: firestore.getPlanLimits('free')
      });

      return res.json({
        status: 'success',
        message: 'Successfully switched to Free plan'
      });
    }

    // Handle custom pricing for business plan
    if (plan === 'business') {
      return res.json({
        status: 'custom',
        message: 'Please contact sales for business plan pricing'
      });
    }

    const amount = PLAN_PRICES[location][plan].price;
    const currency = location === 'india' ? 'INR' : 'USD';

    const order = await razorpay.orders.create({
      amount,
      currency,
      receipt: `rcpt_${Date.now()}`,
      payment_capture: 1,
      notes: {
        userId: req.user.userId,
        plan,
        userLocation: location
      }
    });

    res.json({
      orderId: order.id,
      amount: order.amount,
      currency: order.currency,
      key: process.env.RAZORPAY_KEY_ID
    });
  } catch (error) {
    console.error('Error creating payment order:', error);
    res.status(500).json({ error: 'Failed to create payment order' });
  }
});

// Verify payment endpoint
router.post('/verify', authenticateToken, async (req, res) => {
  const {
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature,
    plan,
    userLocation = 'usa'
  } = req.body;

  try {
    // Verify signature
    const shasum = crypto.createHmac('sha256', process.env.RAZORPAY_KEY_SECRET);
    shasum.update(`${razorpay_order_id}|${razorpay_payment_id}`);
    const digest = shasum.digest('hex');

    if (digest !== razorpay_signature) {
      return res.status(400).json({ error: 'Invalid payment signature' });
    }

    // Get order details to verify amount and currency
    const order = await razorpay.orders.fetch(razorpay_order_id);
    const location = userLocation.toLowerCase();
    const expectedAmount = PLAN_PRICES[location][plan].price;

    if (order.amount !== expectedAmount) {
      return res.status(400).json({ error: 'Invalid payment amount' });
    }

    // Create payment record
    const validFrom = new Date();
    const validUntil = new Date();
    validUntil.setMonth(validUntil.getMonth() + 1);

    const paymentRecord = await firestore.createPaymentRecord({
      userId: req.user.userId,
      orderId: razorpay_order_id,
      paymentId: razorpay_payment_id,
      razorpaySignature: razorpay_signature,
      plan,
      amount: order.amount,
      currency: order.currency,
      status: 'success',
      validFrom,
      validUntil,
      metadata: {
        userLocation: location
      }
    });

    // Update user's plan
    await firestore.db.collection('users').doc(req.user.userId).update({
      plan,
      limits: firestore.getPlanLimits(plan),
      lastPaymentId: paymentRecord.id
    });

    res.json({
      status: 'success',
      message: 'Payment verified and plan updated successfully'
    });
  } catch (error) {
    console.error('Error verifying payment:', error);
    res.status(500).json({ error: error.message || 'Failed to verify payment' });
  }
});

// Payment history endpoint
router.get('/payment-history', authenticateToken, async (req, res) => {
  try {
    const payments = await firestore.getUserPaymentHistory(req.user.userId);
    res.json({ payments });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

export default router;